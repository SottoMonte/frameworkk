# import necessary packages 
from sqlalchemy.ext.asyncio import async_sessionmaker
import sqlalchemy as db
from sqlalchemy import update,delete,insert
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
import framework.port.persistence as port
import framework.service.flow as flow
import importlib

#sqlacodegen 

class adapter(port.port):
    
    omm = dict({})

    def __init__(self,**constants):
        self.config = constants['config']
        self.capabilities = {'speed': 'medium', 'latency': 'medium'}
        self.engine = create_async_engine(f"mysql+asyncmy://{self.config['username']}:{self.config['password']}@{self.config['host']}/{self.config['name']}")
        #self.conn = self.engine.connect()
        self.metadata = db.MetaData()
        #self.Session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        self.async_session = async_sessionmaker(self.engine, future=True, expire_on_commit=False)
        #self.Session = sessionmaker(bind=self.engine) 
        #self.session = self.Session()

    def build(self,table_name):
        Base = declarative_base()
        repository = importlib.import_module(f"framework.repository.{table_name}", package=None)
        columns = []

        for key,attr in repository.scheme:
            li = [key]
            attributes = dict()
            for a in attr:
                match a:
                    case 'Integer': li.append(db.Integer)
                    case 'String': li.append(db.String)
                    case 'DateTime': li.append(db.DateTime)
                    case 'Float': li.append(db.Float)
            
            if 'primary_key' in attr:
                attributes['primary_key'] = True
                #columns.append(db.Column(*li,primary_key=True))
            if 'nullable' in attr:
                attributes['nullable'] = True
                #columns.append(db.Column(*li,nullable=True))

            columns.append(db.Column(*li,**attributes))

        class model(Base):
            __table__ = db.Table(repository.location[self.config['profile'].upper()], Base.metadata,*columns)

        return model

    async def query(self,**constants):

        if constants['model'] not in self.omm:
            model = self.build(constants['model'])
        else:
            model = self.omm[constants['model']]

        #print(constants)

        page_number = int(constants['page']) if 'page' in constants else 1
        #if int(constants['page']) != 0 else 1
        items_per_page = int(constants['row']) if 'row' in constants else 5
        identifier = constants['id'] if 'id' in constants else None
        #identifier = int(''.join(filter(str.isdigit, identifier)))
        #page_number = 2
        #items_per_page = 10
        print(page_number,items_per_page,(page_number-1) * items_per_page)
        #(page_number-1) * items_per_page

        if identifier:
            stmt = select(model).where(model.id == identifier)
        else:
            stmt = select(model).offset((page_number-1) * items_per_page).limit(items_per_page)

        return stmt,model
    
    @flow.asyn(ports=('storekeeper',))
    async def read(self, storekeeper, **constants):
        query,model = await self.query(**constants)

        out = []
        
        async with self.engine.begin() as conn:
            #id = int("".join(ch for ch in constants['identifier'] if ch.isdigit()))
            #result = await conn.execute(select(model).where(model.id == id))
            result = await conn.execute(query)
            for x in result.all():
                out.append({c: str(getattr(x, c)) for c in model.__table__.columns.keys()})
        ggg = dict()

        if len(out) > 1:
            for x in out[0]:
                ggg[x] = [] 
                for y in out:
                    ggg[x].append(y[x])
        elif len(out) == 1:
            ggg = out[0]
        else:
            pass

        if len(out) != 0:
            return storekeeper.builder('transaction',{'state': True,'action':'read','result':ggg})
        else:
            return storekeeper.builder('transaction',{'state': False,'action':'read','remark':'not found data'})

    @flow.asyn(ports=('storekeeper',))
    async def create(self, storekeeper, **constants):
        storekeeper = constants['storekeeper']
        model = await self.query(**constants)

        try:
            #a = self.session.execute(insert(model),[constants['value']])
            async with self.engine.begin() as conn:
                id = int("".join(ch for ch in constants['identifier'] if ch.isdigit()))
                result = await conn.execute(insert(model).values(**constants['value']))
                return storekeeper.builder('transaction',{'state': True,'remark':f"new identifier:{constants['identifier']} created"})
        except SQLAlchemyError as e:
            error = str(e)
            print(error)
            return storekeeper.builder('transaction',{'state': False,'remark':f"{error}"})

    # delete
    @flow.asyn(ports=('storekeeper',))
    async def delete(self, storekeeper, **constants):
        storekeeper = constants['storekeeper']
        model = await self.query(**constants)

        try:
            async with self.engine.begin() as conn:
                id = int("".join(ch for ch in constants['identifier'] if ch.isdigit()))
                qq = delete(model).where(model.id == id)
                result = await conn.execute(qq)
                return storekeeper.builder('transaction',{'state': True,'remark':f"deleted identifier:{constants['identifier']}"})
        except SQLAlchemyError as e:
            error = str(e.__dict__['orig'])
            return storekeeper.builder('transaction',{'state': False,'remark':f"{error}"})

    async def write(self,**constants):
        model = await self.query(**constants)

        try:
            async with self.engine.begin() as conn:
                id = int("".join(ch for ch in constants['identifier'] if ch.isdigit()))
                result = await conn.execute(update(model).where(model.id == id).values(**constants['value']))
        except SQLAlchemyError as e:
            error = str(e.__dict__['orig'])
            print(error)
            return error

    async def tree(self,**constants):
        pass