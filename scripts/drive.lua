-- drive.lua -- inserts a coin, starts the game and DRIVES, never leaving the machine.
--
-- Any set of the family: coin, start, throttle and the digital steering are looked up under every
-- name the family gives them, plus the analogue accelerator where a board has one (Wheels & Fire,
-- whose wheel is analogue too and is left centred, so the car goes straight). Where the set has a
-- gear lever (Wheels & Fire's Gear Shift, a toggle), the pedal is the throttle and the lever is
-- tapped once into high as the driving starts.
--
-- It deliberately does not leave the machine (unlike nav-phase.lua, which calls machine:exit()
-- when its work is done): who decides when to stop is whoever is capturing, with -seconds_to_run.
--
-- Env: COIN_FRAME (200), START_FRAME (320), STEER=0 to go straight.
--      The frames are screen:frame_number()'s, the same ones that name the captures.

local COIN_FRAME = tonumber(os.getenv("COIN_FRAME") or "200")
local START_FRAME = tonumber(os.getenv("START_FRAME") or "320")
local STEER = os.getenv("STEER") ~= "0"

local screen = manager.machine.screens[":screen"]
local p1 = manager.machine.ioport.ports[":P1"]
if not p1 then
    emu.print_error("__DRIVE INVALID: this system has no :P1 port")
    manager.machine:exit()
    return
end

-- Each control under every name the family uses for it: the field names differ from one game to
-- another, and a control that is missing is reported below as INVALID, never left untouched.
local function field(...)
    for _, n in ipairs({ ... }) do
        if p1.fields[n] then return p1.fields[n] end
    end
    return nil
end

local coin = field("Coin 1", "Coin")
local start = field("1 Player Start", "P1 Start", "Start 1")
local lever = p1.fields["Gear Shift"]
local throttle = (not lever) and field("P1 Button 1", "P1 Button 1 A", "Button 1") or nil
local left = field("P1 Left")
local right = field("P1 Right")
-- An analogue accelerator lives on a port of its own (Wheels & Fire's); where the machine has one,
-- it is pressed to the floor.
local pedal
for _, port in pairs(manager.machine.ioport.ports) do
    pedal = pedal or port.fields["Accelerator Pedal"]
end

-- A list and not a table keyed by name: a nil value leaves its key out of a table constructor, so
-- `pairs` would never visit the very control that is missing.
local needed = { { "coin", coin }, { "start", start } }
if lever then
    table.insert(needed, { "accelerator pedal", pedal })
else
    table.insert(needed, { "throttle", throttle })
end
for _, c in ipairs(needed) do
    if not c[2] then
        emu.print_error(string.format("__DRIVE INVALID: control '%s' is missing", c[1]))
        manager.machine:exit()
        return
    end
end

-- A 40-frame press: plenty for the game to read it, and not so long that it counts twice.
local HOLD = 40

_G._drive = emu.add_machine_frame_notifier(function()
    local f = screen:frame_number()
    coin:set_value((f >= COIN_FRAME and f < COIN_FRAME + HOLD) and 1 or 0)
    start:set_value((f >= START_FRAME and f < START_FRAME + HOLD) and 1 or 0)
    if f < START_FRAME + HOLD then return end

    if throttle then throttle:set_value(1) end
    if pedal then pedal:set_value(pedal.maxvalue) end
    -- the lever stays where a press leaves it, so one frame shifts to high for the rest of the run
    if lever then lever:set_value((f == START_FRAME + HOLD) and 1 or 0) end
    -- A slow weave: going straight leaves the track almost at once, and a full turn every frame
    -- gives a trajectory no player makes, which leads to odd corners of the track.
    if STEER and left and right then
        local t = (f - START_FRAME) % 240
        left:set_value(t < 60 and 1 or 0)
        right:set_value((t >= 120 and t < 180) and 1 or 0)
    end
end)
