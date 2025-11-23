modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'SUPABASE': ['services']},
    model = 'service',
    mapper = {},
)