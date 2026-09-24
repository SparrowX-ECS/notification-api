# Notification API repository structure

The Notification API follows the shared SparrowX backend structure. `src/database.py` owns PostgreSQL configuration, `src/models.py` owns persistence models, `src/schemas.py` owns API validation, and `src/routes/notifications.py` owns notification endpoints. The application starts from `src.main:app`.
