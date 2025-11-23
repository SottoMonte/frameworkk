modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'SUPABASE': ['containers']},
    model = 'container',
    mapper = {
        'identifier': {'GITHUB': 'id', 'SUPABASE': 'user.id'},
        'username': {'GITHUB': 'login'},
        'role': {'GITHUB': 'type', 'SUPABASE': 'user.role'},
        'avatar': {'GITHUB': 'avatar_url'},
    },
)