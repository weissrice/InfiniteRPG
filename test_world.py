from engine.world import create_new_game


game = create_new_game()

print("WORLD:", game.world.name)
print("GENRE:", game.world.genre)

print("\nPLAYER")
print("Name:", game.player.name)
print("HP:", game.player.hp)
print("Location:", game.player.location)
print("Inventory:", game.player.inventory)

print("\nCURRENT LOCATION")

location = game.current_location()

if location:
    print("Name:", location.name)
    print("Description:", location.description)
    print("Exits:", list(location.exits.keys()))
    print("Items:", location.items)