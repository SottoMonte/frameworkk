resources = {
    'factory': 'framework/service/factory.py',
    'product': 'application/model/product.json',
}

repository = factory.repository(
    location = {'SUPABASE': ['products']},
    model = product,
    mapper = {},
)