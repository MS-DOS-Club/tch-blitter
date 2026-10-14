-- oracle.lua -- autoboot script: snapshots of Radical Enduro's boot at fixed frames, then exits.
--
-- Launched with: -autoboot_script scripts/radendur/oracle.lua -snapname '%i'
-- The target frames can be set through the ORACLE_FRAMES environment variable (comma separated).

local frames_env = os.getenv("ORACLE_FRAMES") or "300,600,900"
local targets = {}
for n in string.gmatch(frames_env, "%d+") do
    targets[#targets + 1] = tonumber(n)
end

local count = 0
local idx = 1

-- kept in a global, or Lua's collector frees the notifier and it stops firing
oracle_sub = emu.add_machine_frame_notifier(function()
    count = count + 1
    if idx <= #targets and count >= targets[idx] then
        manager.machine.video:snapshot()
        idx = idx + 1
        if idx > #targets then
            manager.machine:exit()
        end
    end
end)
