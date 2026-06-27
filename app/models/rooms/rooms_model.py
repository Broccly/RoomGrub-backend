from sqlalchemy import Connection, text

def create_room_query(conn: Connection, room):
  query = text("""
    INSERT INTO Rooms (members, admin, uid)
    VALUES (:members, :admin, :uid)
    RETURNING 
  """)

  params = {
    "members": room.members,
    "admin": room.admin,
    "uid": room.uid
  }

  return conn.execute(query, params)