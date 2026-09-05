import django
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from drf_spectacular.generators import SchemaGenerator
gen = SchemaGenerator()
schema = gen.get_schema(request=None, public=True)
paths = list(schema.get('paths', {}).keys())
print(f"Total API paths: {len(paths)}")
for p in sorted(paths):
    print(f"  {p}")
