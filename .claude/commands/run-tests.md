Run the RoomGrub test suite.

```bash
pytest -v
```

To run a specific test file:
```bash
pytest tests/test_rooms.py -v
```

To run a specific test:
```bash
pytest tests/test_rooms.py::test_create_room -v
```
