modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'SUPABASE': ['servers']},
    model = 'server',
    mapper = {
        #'identifier': {'SUPABASE': 'user.id'},
        #'username': {'GITHUB': 'login'},
        #'role': {'GITHUB': 'type', 'SUPABASE': 'user.role'},
        #'avatar': {'GITHUB': 'avatar_url'},
    },
)