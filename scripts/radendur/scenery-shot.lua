-- scenery-shot.lua -- drives the desert race (../drive.lua) and photographs one frame of it, for the
-- goldens that watch radendurh's scenery layer: the boot and starting-line goldens never
-- reach a stretch where that layer draws anything the prototype's own engine would not.
--
-- It writes `SHOT f=<frame> view x=<x> y=<y>` to OUT when it takes the picture, so a bless can
-- refuse a capture of the wrong place: the view origin is the game's own (0x201736, 0x201738).
-- Then it leaves the machine, so the run costs the frames up to the shot and no more.
--
-- Env: SHOT_FRAME (required: the screen:frame_number() to photograph; the caller owns the choice),
--      OUT (required, ABSOLUTE: the log the SHOT line goes to), and drive.lua's own.

local here = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") or "."
local SHOT_FRAME = tonumber(os.getenv("SHOT_FRAME") or "")
local OUT = os.getenv("OUT")
-- absolute on either host: MSYS2 hands a Windows MAME its environment's paths as C:/...
local function is_absolute(p) return p:sub(1, 1) == "/" or p:match("^%a:[/\\]") ~= nil end
if not SHOT_FRAME or not OUT or not is_absolute(OUT) then
    emu.print_error("__SCENERY: INVALID -- SHOT_FRAME must be a frame number and OUT an absolute path")
    manager.machine:exit()
    return
end
local log = assert(io.open(OUT, "w"))
local space = manager.machine.devices[":maincpu"].spaces["program"]
local screen = manager.machine.screens[":screen"]

_G._scenery_shot = emu.add_machine_frame_notifier(function()
    if screen:frame_number() ~= SHOT_FRAME then return end
    manager.machine.video:snapshot()
    log:write(string.format("SHOT f=%d view x=%d y=%d\n", SHOT_FRAME,
        space:read_u16(0x201736), space:read_u16(0x201738)))
    log:close()
    manager.machine:exit()
end)

dofile(here .. "/../drive.lua")
