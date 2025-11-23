modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'GITHUB': ['user'], 'SUPABASE': ['secrets']},
    model = 'secret',
    mapper = {},
)