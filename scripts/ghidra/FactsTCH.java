// FactsTCH.java -- what Ghidra's analysis of one image knows, as JSON for ghidra-labels.py and
// verify-listings.py: every function with its body, every named symbol with what sits under it (an
// instruction start, the middle of one, data, nothing), and every reference into the hardware
// window with its function.
//
// Usage: analyzeHeadless <proj> tch -process [<img.bin>] -noanalysis -readOnly \
//          -scriptPath scripts/ghidra -postScript FactsTCH.java <output directory>
// It writes <output directory>/<program name>.json, one per program processed.
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import java.io.File;
import java.io.PrintWriter;

public class FactsTCH extends GhidraScript {
    // The board's hardware window: every port of the family lives in 0x700000-0x7fffff.
    private static final long HW_LO = MemoryMapTCH.HW_START,
        HW_HI = MemoryMapTCH.HW_START + MemoryMapTCH.HW_SIZE - 1;

    private static String q(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    // What the listing holds at an address: the question a symbol's claim is checked against.
    private String kindAt(Listing lst, Address a) {
        CodeUnit cu = lst.getCodeUnitContaining(a);
        if (cu == null) return "none";
        boolean start = cu.getMinAddress().equals(a);
        if (cu instanceof Instruction) return start ? "insn" : "mid_insn";
        Data d = (Data) cu;
        if (!d.isDefined()) return "undefined";
        return start ? "data" : "mid_data";
    }

    // Where the code unit holding the address starts: for a symbol in the middle of an
    // instruction, the instruction the flow actually decoded there.
    private String unitAt(Listing lst, Address a) {
        CodeUnit cu = lst.getCodeUnitContaining(a);
        return cu == null ? "null" : Long.toString(cu.getMinAddress().getOffset());
    }

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: FactsTCH.java <output dir>");
        File dir = new File(args[0]);
        if (!dir.isDirectory()) throw new IllegalArgumentException("not a directory: " + dir);
        String prog = currentProgram.getName().replaceAll("\\.bin$", "");
        File outFile = new File(dir, prog + ".json");
        Listing lst = currentProgram.getListing();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();

        try (PrintWriter out = new PrintWriter(outFile, "UTF-8")) {
            out.println("{");
            out.println("  \"program\": " + q(prog) + ",");

            out.println("  \"functions\": [");
            boolean first = true;
            for (Function f : fm.getFunctions(true)) {
                StringBuilder body = new StringBuilder();
                for (AddressRange r : f.getBody()) {
                    if (body.length() > 0) body.append(", ");
                    body.append("[").append(r.getMinAddress().getOffset()).append(", ")
                        .append(r.getMaxAddress().getOffset()).append("]");
                }
                out.print((first ? "" : ",\n") + "    {\"entry\": " + f.getEntryPoint().getOffset()
                    + ", \"name\": " + q(f.getName()) + ", \"body\": [" + body + "]}");
                first = false;
            }
            out.println("\n  ],");

            // Every symbol a person or a script named; Ghidra's own FUN_/LAB_/DAT_ are DEFAULT.
            out.println("  \"symbols\": [");
            first = true;
            for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(false)) {
                if (s.getSource() == SourceType.DEFAULT || s.isExternal()) continue;
                Address a = s.getAddress();
                if (!a.isMemoryAddress()) continue;
                Function in = fm.getFunctionContaining(a);
                out.print((first ? "" : ",\n") + "    {\"addr\": " + a.getOffset()
                    + ", \"name\": " + q(s.getName())
                    + ", \"source\": " + q(s.getSource().toString())
                    + ", \"type\": " + q(s.getSymbolType().toString())
                    + ", \"primary\": " + s.isPrimary()
                    + ", \"kind\": " + q(kindAt(lst, a))
                    + ", \"unit\": " + unitAt(lst, a)
                    + ", \"function_start\": " + (fm.getFunctionAt(a) != null)
                    + ", \"in_function\": " + (in == null ? "null" : in.getEntryPoint().getOffset())
                    + "}");
                first = false;
            }
            out.println("\n  ],");

            out.println("  \"hw_refs\": [");
            first = true;
            AddressSet hw = new AddressSet(toAddr(HW_LO), toAddr(HW_HI));
            AddressIterator dests = rm.getReferenceDestinationIterator(hw, true);
            while (dests.hasNext()) {
                Address to = dests.next();
                for (Reference r : rm.getReferencesTo(to)) {
                    Function f = fm.getFunctionContaining(r.getFromAddress());
                    out.print((first ? "" : ",\n") + "    {\"from\": "
                        + r.getFromAddress().getOffset() + ", \"to\": " + to.getOffset()
                        + ", \"type\": " + q(r.getReferenceType().toString())
                        + ", \"function\": " + (f == null ? "null" : f.getEntryPoint().getOffset())
                        + "}");
                    first = false;
                }
            }
            out.println("\n  ]");
            out.println("}");
        }
        println("facts " + prog + " -> " + outFile);
    }
}
