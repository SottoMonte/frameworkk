modules = {'factory': 'framework.service.factory',}

repository = factory.repository(
    location = {'SUPABASE': ['notes']},
    model = 'note',
    mapper = {},
)