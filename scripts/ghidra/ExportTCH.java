// ExportTCH.java -- export GhidraScript over a program that is ALREADY analysed.
// Appends to a text file: the function count and list, the functions that
// reference the blitter (0x700000-0x70001f) and the decompiled pseudo-C of the
// boot function (reset). It is the readable material for reviewing the logic
// without opening the GUI.
//
// Usage: analyzeHeadless <proj> tch -process <img.bin> -noanalysis \
//          -scriptPath scripts/ghidra -postScript ExportTCH.java <output_file>
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class ExportTCH extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(args[0], true));
        String prog = currentProgram.getName();
        FunctionManager fm = currentProgram.getFunctionManager();

        out.println("################################################################");
        out.println("# " + prog + "   functions: " + fm.getFunctionCount());
        out.println("################################################################");
        for (Function f : fm.getFunctions(true)) {
            out.println(String.format("  %-8s  %-24s  %d bytes",
                f.getEntryPoint().toString(), f.getName(), f.getBody().getNumAddresses()));
        }

        // The labels seeded from symbols.txt would not appear in a function listing:
        // Ghidra creates them as labels, not functions, so the knowledge seeded there
        // would never reach the versioned artefact. They are listed on their own, which
        // also shows at a glance what is identified in each image.
        out.println("\n-- symbols seeded from symbols.txt --");
        int nsim = 0;
        for (ghidra.program.model.symbol.Symbol sym :
                currentProgram.getSymbolTable().getAllSymbols(false)) {
            String n = sym.getName();
            // By the symbol's source, as FactsTCH and ListTCH read it: a name prefix lets through
            // the names the analysis makes itself (thunk_FUN_...) as if the table had given them.
            if (sym.getSource() != ghidra.program.model.symbol.SourceType.USER_DEFINED) continue;
            out.println(String.format("  %-8s  %s", sym.getAddress(), n));
            nsim++;
        }
        if (nsim == 0) out.println("  (none)");

        out.println("\n-- code that touches the blitter (0x700000-0x70001f) --");
        ReferenceManager rm = currentProgram.getReferenceManager();
        Set<String> hits = new LinkedHashSet<>();
        for (long a = MemoryMapTCH.BLITTER_START; a <= MemoryMapTCH.BLITTER_LAST; a++) {
            Address t = toAddr(a);
            for (Reference r : rm.getReferencesTo(t)) {
                Function f = fm.getFunctionContaining(r.getFromAddress());
                String fn = (f != null) ? f.getName() + " @ " + f.getEntryPoint() : "(no function)";
                hits.add(String.format("  %s -> %s   [%s]", r.getFromAddress(), t, fn));
            }
        }
        for (String h : hits) out.println(h);
        if (hits.isEmpty()) out.println("  (no direct reference detected)");

        // Pseudo-C of the boot function (reset)
        out.println("\n-- decompilation of reset --");
        Function reset = fm.getFunctionAt(toAddr(getInt(toAddr(0x4)) & 0xffffffffL));
        if (reset != null) {
            DecompInterface di = new DecompInterface();
            di.openProgram(currentProgram);
            DecompileResults res = di.decompileFunction(reset, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("  (decompilation not completed)");
            }
            di.dispose();
        } else {
            out.println("  (reset function not found)");
        }
        out.println();
        out.close();
        println("exported " + prog + " -> " + args[0]);
    }
}
