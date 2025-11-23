resources = {
    'factory': 'framework/service/factory.py',
    'domain': 'application/model/domain.json',
}

repository = factory.repository(
    location = {'SUPABASE': ['domains']},
    model = domain,
    mapper = {},
)