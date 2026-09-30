# AppVisitas Flutter

Cliente Flutter para la API de AppVisitas. Implementa autenticación, perfil,
administración territorial, equipo pastoral, hermanos, visitas, auditoría y
rankings.

## Desarrollo

Requiere Flutter 3.x. Desde esta carpeta:

```bash
flutter pub get
flutter test
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 5000 --dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Configura la API y PostgreSQL siguiendo el [README del proyecto](../README.md)
y [INSTRUCTIONS.md](../INSTRUCTIONS.md). Las operaciones protegidas requieren
una sesión autenticada; la autorización efectiva siempre se valida en backend.
