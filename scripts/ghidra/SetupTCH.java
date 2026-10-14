// SetupTCH.java -- pre-analysis GhidraScript for TCH's 68000 images.
// Runs as a -preScript BEFORE auto-analysis to seed it: creates the RAM/IO
// blocks, marks the entry from the reset vector (a long at 0x4), seeds the ROM
// targets of the other vectors and applies the labels of disasm/symbols.txt, each
// with its description as a plate comment, and disassembles the code the game
// runs from a RAM copy ("@code" lines). With the entry seeded, auto-analysis follows the
// calls and discovers the functions. Java (not Python) so it runs headless
// without PyGhidra.
//
// Usage: analyzeHeadless ... -preScript SetupTCH.java <symbols.txt> [<executed addresses>]
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;

public class SetupTCH extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String symbolsPath = args.length > 0 ? args[0] : null;
        Memory mem = currentProgram.getMemory();

        // Ghidra's address-table heuristic finds much of these games' code through their jump
        // tables, and at its default it also takes two or three code words that look like
        // addresses for a table: it types a jsr's operand as a pointer, or starts code inside an
        // instruction. Four consecutive addresses, chosen against the addresses MAME executes
        // (the commit that sets it holds the comparison), keep the tables and drop the impostors.
        setAnalysisOption(currentProgram, "Create Address Tables.Minimum Table Size", "4");

        // Uninitialised blocks for RAM / IO: references resolve to a named target
        // and are not misread as code.
        long[][] blocks = { {MemoryMapTCH.RAM_START, MemoryMapTCH.RAM_SIZE},
                             {MemoryMapTCH.HW_START, MemoryMapTCH.HW_SIZE} };
        String[] names = { "RAM", "IO" };
        for (int i = 0; i < blocks.length; i++) {
            Address a = toAddr(blocks[i][0]);
            if (mem.getBlock(a) == null) {
                try {
                    mem.createUninitializedBlock(names[i], a, blocks[i][1], false);
                    println("block " + names[i] + " @ 0x" + Long.toHexString(blocks[i][0]));
                } catch (Exception e) {
                    println("WARN block " + names[i] + ": " + e.getMessage());
                }
            }
        }

        // Entry = the big-endian long at 0x4 (the 68000's reset vector).
        try {
            long pc = getInt(toAddr(0x4)) & 0xffffffffL;
            Address entry = toAddr(pc);
            disassemble(entry);
            createFunction(entry, "reset");
            addEntryPoint(entry);
            println("entry (reset) = 0x" + Long.toHexString(pc));
        } catch (Exception e) {
            println("WARN entry: " + e.getMessage());
        }

        // The raw loader names the image's block "ram"; it is the program ROM, and every listing
        // prints the block's name.
        ghidra.program.model.mem.MemoryBlock rom = mem.getBlock(toAddr(0));
        if (rom != null) rom.setName("ROM");

        // The vector table is 256 longs of pointers: typed as such, so a listing shows each
        // vector as the address it holds and never as bytes nobody reached.
        for (long v = 0; v < MemoryMapTCH.VECTORS_END; v += 4) {
            try { createDWord(toAddr(v)); } catch (Exception e) { /* already defined */ }
        }

        // Nothing calls an exception, interrupt or TRAP handler, so the flow from the reset never
        // finds one: each ROM target of the vectors 0x08..0xbc is seeded as a function. A vector
        // pointing into RAM (a handler copied there) or at the reset is left alone.
        long resetPc = getInt(toAddr(0x4)) & 0xffffffffL;
        java.util.TreeSet<Long> handlers = new java.util.TreeSet<>();
        for (long v = 0x08; v <= 0xbc; v += 4) {
            long t = getInt(toAddr(v)) & 0xffffffffL;
            if (MemoryMapTCH.inCode(t) && (t & 1) == 0 && t != resetPc) handlers.add(t);
        }
        for (long t : handlers) {
            Address a = toAddr(t);
            disassemble(a);
            if (getFunctionAt(a) == null) createFunction(a, null);
        }
        println(handlers.size() + " vector targets seeded");

        // Addresses the machine executed (disasm/executed/<image>.txt, the second argument when
        // the image has one): instruction starts by definition, disassembled before any heuristic
        // of the analysis can type them as data or start an instruction across them.
        if (args.length > 1) {
            int seeded = 0;
            try (BufferedReader er = new BufferedReader(new FileReader(args[1]))) {
                String line;
                while ((line = er.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty() || line.startsWith("#")) continue;
                    Address at = toAddr(Long.parseLong(line.substring(2), 16));
                    disassemble(at);
                    if (getInstructionAt(at) == null)
                        throw new IllegalStateException("executed address left no instruction: " + at);
                    seeded++;
                }
            }
            println(seeded + " executed addresses seeded");
        }

        // Labels from symbols.txt ("<hexaddr>  <label>  <desc>").
        if (symbolsPath != null) {
            File f = new File(symbolsPath);
            if (f.exists()) {
                BufferedReader br = new BufferedReader(new FileReader(f));
                String line;
                int n = 0, skipped = 0, code = 0;
                // One game's addresses do NOT hold for another: 0xe5300 is different code
                // in each binary. An "@image <part>" line opens a block that applies only to
                // the images whose name contains that part; "@image *" returns to what is
                // common (hardware map, vectors). With no marker, a label applies to all.
                String image = currentProgram.getName();
                boolean apply = true;
                while ((line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.startsWith("@image")) {
                        String filter = line.substring(6).trim();
                        apply = filter.equals("*");
                        for (String part : filter.split(","))
                            if (!part.trim().isEmpty() && image.contains(part.trim()))
                                apply = true;
                        continue;
                    }
                    if (line.isEmpty() || line.startsWith("#")) continue;
                    // "@code <addr>  runs from <ram>": disassembled before the analysis (why:
                    // symbols_model.py's symbols_file), and where it runs joins its plate comment.
                    if (line.startsWith("@code")) {
                        if (!apply) continue;
                        String[] c = line.substring(5).trim().split("\\s+", 2);
                        Address at = toAddr(Long.parseLong(c[0].substring(2), 16));
                        // An earlier @code's flow may already have reached it: what counts is that
                        // an instruction starts there afterwards.
                        disassemble(at);
                        if (getInstructionAt(at) == null)
                            throw new IllegalStateException("@code left no instruction at " + at);
                        if (c.length > 1) {
                            String had = getPlateComment(at);
                            setPlateComment(at, had == null ? c[1] : had + "\n" + c[1]);
                        }
                        code++;
                        continue;
                    }
                    String[] p = line.split("\\s+", 3);
                    if (p.length < 2 || !p[0].startsWith("0x")) continue;
                    if (!apply) { skipped++; continue; }
                    try {
                        Address at = toAddr(Long.parseLong(p[0].substring(2), 16));
                        createLabel(at, p[1], true);
                        // The description travels as the plate comment the listings print
                        // above the label; two symbols at one address keep both.
                        String plate = p[1] + (p.length > 2 ? ": " + p[2] : "");
                        String had = getPlateComment(at);
                        setPlateComment(at, had == null ? plate : had + "\n" + plate);
                        n++;
                    } catch (Exception e) { /* address out of range: ignored */ }
                }
                if (code > 0)
                    println(code + " RAM-run code blocks disassembled");
                if (skipped > 0)
                    println(skipped + " labels of other images, skipped");
                br.close();
                println(n + " labels applied from symbols.txt");
            }
        }
    }
}
