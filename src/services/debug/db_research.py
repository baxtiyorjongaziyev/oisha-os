
from database import Database
db = Database()
print("TEAM ROLES:")
for user in db.get_team_roles():
    print(f"{user['user_id']} | {user['name']} | {user['role']}")
