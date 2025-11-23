imports = {
    'factory': 'framework/service/factory.py',
    'scheme': 'framework/scheme/session.json'
}

def repository():
    return factory.repository(
    location = {'SESSION': ['{{filter.identifier}}','{{payload.identifier}}'], 'SUPABASE': ['inventories']},
    model = scheme,
    )

""" mapper = {
        'identifier': {'GITHUB': 'id', 'SUPABASE': 'user.id'},
        'username': {'GITHUB': 'login'},
        'role': {'GITHUB': 'type', 'SUPABASE': 'user.role'},
        'avatar': {'GITHUB': 'avatar_url'},
    },"""