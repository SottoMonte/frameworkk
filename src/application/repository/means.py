resources = {
    'factory': 'framework/service/factory.py',
    'media': 'application/model/media.json',
}

repository = factory.repository(
    location = {'SUPABASE': ['means']},
    model = media,
    mapper = {},
)