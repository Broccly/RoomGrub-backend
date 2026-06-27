from app.models.rooms.rooms_model import create_room_query

def create_room(request, conn):
  
  result = create_room_query()
  return result