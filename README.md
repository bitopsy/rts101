# rts101 (Total Recursion)

rts101 is a minimal Real-Time Strategy (RTS) game inspired by *Total Annihilation* and *Beyond All Reason*. It implements core RTS mechanics (economy, base building, unit production, AI, and combat) in less than 2,000 lines of Python code and a total package size under 100KB.

## Specs
- **Language:** Python 3.x
- **Engine:** Pygame
- **Code Size:** < 2,000 lines
- **Package Size:** < 100 KB
- **Features:** Fullscreen support, dynamic zoom/pan camera, minimal AI, and procedural terrain.

## Gameplay
The goal is to eliminate the enemy Commander. You start with a single Commander who can build structures and produce units.
- **Economy:** Manage Metal and Energy. Build Solar Collectors for energy and Metal Extractors on deposits for metal.
- **Build Range:** Structures must be placed within the Commander's build range.
- **Production:** Factories produce units. Factories must be within the Commander's production range to operate.
- **Controls:**
  - `Left Click / Drag`: Select units/buildings.
  - `Right Click`: Move units, attack targets, or set rally points.
  - `Tab`: Quickly select the Commander.
  - `1-0 Keys`: Build structures (when Commander is selected) or queue units (when Factory is selected).
  - `X`: Cancel the last item in a production queue.
  - `Del / Backspace`: Self-destruct selected units/buildings.
  - `+/- / Scroll`: Zoom in and out.
  - `Arrows / WASD`: Pan the camera.

## Units & Buildings

### Buildings
- **Commander**: The heart of your army. Can move, build structures, and fight. If it dies, you lose.
- **Solar Collector**: Generates energy.
- **Metal Extractor**: Extracts metal from deposits.
- **Factory**: Produces basic ground units.
- **Advanced Lab**: Produces advanced units (Tanks, Artillery, Raiders).
- **Air Pad**: Produces aircraft (Fighters, Bombers).
- **Shipyard**: Produces naval units (Gunboats, Carriers).
- **Laser Turret**: Basic defensive structure.
- **AA Gun**: Specialized anti-air defense.
- **Coastal Battery**: Powerful long-range naval defense.
- **Shield Generator**: Creates a protective shield for nearby friendly units.

### Units
- **Scout**: Fast, low health, used for exploration.
- **Soldier**: Basic infantry.
- **Tank**: Strong ground combat unit.
- **Artillery**: Long-range siege unit.
- **Raider**: Fast attack unit with laser weapons.
- **Fighter**: Fast air-to-air and air-to-ground combat.
- **Bomber**: Heavy air-to-ground attack unit.
- **Gunboat**: Standard naval combatant.
- **Carrier**: Large naval vessel, strong against other ships.
