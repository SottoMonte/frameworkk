modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'GITHUB': ['user'], 'SUPABASE': ['inventories']},
    mapper = {
        'identifier': {'GITHUB': 'id', 'SUPABASE': 'user.id'},
        'username': {'GITHUB': 'login'},
        'role': {'GITHUB': 'type', 'SUPABASE': 'user.role'},
        'avatar': {'GITHUB': 'avatar_url'},
    },
)