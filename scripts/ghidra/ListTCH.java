// ListTCH.java -- an image's annotated listing, written from the recursive analysis rather than a
// straight walk: instructions, typed data as dc.*, one line per range the flow never reached, the
// table's labels with their descriptions (SetupTCH.java's plate comments), and the registers.yaml
// name beside each read or write of a board register. Immediates and address-register displacements
// are numbers unless the table named them.
//
// Usage: analyzeHeadless <proj> tch -process [<img.bin>] -noanalysis -readOnly \
//          -scriptPath scripts/ghidra -postScript ListTCH.java <out dir> <ports.tsv> [suspects.tsv]
// It writes <out dir>/<program name>.lst; ports.tsv is scripts/port_names.py's, suspects.tsv
// verify-listings.py's list of the lines to mark.
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.CodeUnitFormat;
import ghidra.program.model.listing.CodeUnitFormatOptions;
import ghidra.program.model.listing.CodeUnitIterator;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ListTCH extends GhidraScript {
    private PrintWriter out;
    private Listing listing;
    private CodeUnitFormat format;
    private final Map<Long, String> ports = new HashMap<>();
    private final java.util.Set<Long> suspects = new java.util.HashSet<>();
    // verify-listings.py's word for a line its 68000-only disassembler refuses: Ghidra's language is
    // a 68040's, so its heuristics can decode data or an operand as an instruction no 68000 has.
    static final String SUSPECT = "  ; not 68000 code: the analysis decoded data or an operand here";

    private static String hex(byte[] b, int max) {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < Math.min(b.length, max); i++) s.append(String.format("%02x", b[i] & 0xff));
        return s.toString();
    }

    // Our names and Ghidra's, primary first, so the line a reference shows is the first one read.
    private List<Symbol> labelsAt(Address a) {
        List<Symbol> syms = new ArrayList<>();
        for (Symbol s : currentProgram.getSymbolTable().getSymbols(a)) syms.add(s);
        syms.sort(Comparator.comparing((Symbol s) -> s.isPrimary() ? 0 : 1)
            .thenComparing((Symbol s) -> s.getName()));
        return syms;
    }

    private boolean named(Address a) {
        for (Symbol s : currentProgram.getSymbolTable().getSymbols(a))
            if (s.getSource() != SourceType.DEFAULT) return true;
        return listing.getComment(CodeUnit.PLATE_COMMENT, a) != null;
    }

    private void head(Address a) {
        if (listing.getFunctionAt(a) != null) out.println();
        String plate = listing.getComment(CodeUnit.PLATE_COMMENT, a);
        if (plate != null) {
            out.println();
            for (String line : plate.split("\n")) wrap(line);
        }
        for (Symbol s : labelsAt(a)) out.println(s.getName() + ":");
    }

    // A description is one long line in the data; a reader gets it at a hundred columns.
    private void wrap(String text) {
        StringBuilder line = new StringBuilder(";");
        for (String word : text.split(" ")) {
            if (line.length() + 1 + word.length() > 100 && line.length() > 1) {
                out.println(line);
                line = new StringBuilder(";  ");
            }
            line.append(' ').append(word);
        }
        out.println(line);
    }

    private void gap(long from, long to) {
        out.println(String.format("%08x  ; %08x..%08x  %d bytes the analysis never reached",
            from, from, to, to - from + 1));
    }

    // Only a read or a write is an access: a `lea` or an immediate that merely holds a register's
    // address names nothing yet.
    private String portNote(CodeUnit cu) {
        java.util.LinkedHashSet<String> names = new java.util.LinkedHashSet<>();
        for (Reference r : cu.getReferencesFrom()) {
            if (!r.getReferenceType().isRead() && !r.getReferenceType().isWrite()) continue;
            String n = ports.get(r.getToAddress().getOffset());
            if (n != null) names.add(n);
        }
        return names.isEmpty() ? "" : "  ; " + String.join(", ", names);
    }

    // An immediate or a displacement is a number the code computes with. Ghidra's analysis turns one
    // that happens to equal an address into that address's name (`#PTR_DAT_00007300` for 0x7300,
    // `(wf_zoom_desc_x,A6)` for 0x400(a6)), which names a datum the instruction never touches. Those
    // are written as the number; a name the table gave an immediate, and a stack variable, stay.
    private String rendered(Instruction ins) {
        String rep = format.getRepresentationString(ins);
        for (int i = 0; i < ins.getNumOperands(); i++) {
            String sym = format.getOperandRepresentationString(ins, i);
            String raw = ins.getDefaultOperandRepresentation(i);
            if (sym.equals(raw)) continue;
            boolean immediate = sym.startsWith("#");
            boolean displaced = sym.matches("\\((?!(local|param|Stack)_)[^,]*,(A[0-6]|SP)[),].*");
            if (immediate && !namedByUs(ins, i) || displaced) {
                // a substitution that finds nothing would leave the misleading name in silence
                if (!rep.contains(sym))
                    throw new IllegalStateException(ins.getAddress() + ": operand '" + sym
                        + "' is not in '" + rep + "'");
                rep = rep.replace(sym, raw);
            }
        }
        return rep;
    }

    private boolean namedByUs(Instruction ins, int op) {
        for (Reference r : ins.getOperandReferences(op)) {
            Symbol s = currentProgram.getSymbolTable().getPrimarySymbol(r.getToAddress());
            if (s != null && s.getSource() == SourceType.USER_DEFINED) return true;
        }
        return false;
    }

    // A label the table puts inside an instruction or a datum has no line of its own: it is said
    // above that line, with its offset, rather than lost.
    private void inner(CodeUnit cu) {
        for (long o = 1; o < cu.getLength(); o++) {
            Address a = cu.getMinAddress().add(o);
            for (Symbol s : currentProgram.getSymbolTable().getSymbols(a))
                if (s.getSource() != SourceType.DEFAULT)
                    out.println("; " + s.getName() + " is " + o + " bytes into the next line");
        }
    }

    private void data(Data d) throws Exception {
        int len = d.getLength();
        String dc = len == 1 ? "dc.b" : len == 2 ? "dc.w" : len == 4 ? "dc.l" : null;
        byte[] b = d.getBytes();
        if (dc != null) {
            String target = "";
            for (Reference r : d.getReferencesFrom()) {
                // Only a name somebody gave: Ghidra's address-table pass takes many plain values
                // (0x00020002) for pointers, and a DAT_ there would read as a fact.
                Symbol s = currentProgram.getSymbolTable().getPrimarySymbol(r.getToAddress());
                if (s != null && s.getSource() != SourceType.DEFAULT) target = "  ; -> " + s.getName();
            }
            out.println(String.format("%08x  %-20s  %s 0x%s%s", d.getAddress().getOffset(), hex(b, 10), dc,
                hex(b, 4), target));
            return;
        }
        // A string, an array or a structure: its bytes, sixteen to a line.
        for (int i = 0; i < b.length; i += 16) {
            byte[] row = java.util.Arrays.copyOfRange(b, i, Math.min(b.length, i + 16));
            StringBuilder v = new StringBuilder();
            for (byte x : row) v.append(v.length() == 0 ? "" : ",").append(String.format("0x%02x", x & 0xff));
            out.println(String.format("%08x  %-20s  dc.b %s%s", d.getAddress().getOffset() + i, "", v,
                i == 0 ? "  ; " + d.getDataType().getName() : ""));
        }
    }

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2 || args.length > 3)
            throw new IllegalArgumentException("usage: ListTCH.java <out dir> <ports.tsv> [suspects.tsv]");
        File dir = new File(args[0]);
        if (!dir.isDirectory()) throw new IllegalArgumentException("not a directory: " + dir);
        String prog = currentProgram.getName().replaceAll("\\.bin$", "");
        ports.clear();
        suspects.clear();
        if (args.length == 3) {
            try (BufferedReader br = new BufferedReader(new FileReader(args[2]))) {
                String line;
                while ((line = br.readLine()) != null) {
                    String[] p = line.split("\t");
                    if (p.length == 2 && p[0].equals(prog)) suspects.add(Long.decode(p[1]));
                }
            }
        }
        try (BufferedReader br = new BufferedReader(new FileReader(args[1]))) {
            String line;
            while ((line = br.readLine()) != null) {
                String[] p = line.split("\t");
                if (p.length == 3 && p[0].equals(prog)) ports.put(Long.decode(p[1]), p[2]);
            }
        }
        listing = currentProgram.getListing();
        format = new CodeUnitFormat(CodeUnitFormatOptions.ShowBlockName.NEVER,
            CodeUnitFormatOptions.ShowNamespace.NEVER);
        File outFile = new File(dir, prog + ".lst");
        long instructions = 0;
        try (PrintWriter w = new PrintWriter(outFile, "UTF-8")) {
            out = w;
            out.println("; " + prog + " -- annotated listing, GENERATED by scripts/ghidra/ListTCH.java from the");
            out.println("; Ghidra analysis that disasm/analysis.txt is exported from. Do not edit it: the names and");
            out.println("; comments come from hardware/symbols.yaml, the port names from hardware/registers.yaml.");
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                if (!block.isInitialized()) continue;
                out.println();
                out.println(String.format("; ---- %s  %08x..%08x", block.getName(),
                    block.getStart().getOffset(), block.getEnd().getOffset()));
                CodeUnitIterator it = listing.getCodeUnits(new AddressSet(block.getStart(), block.getEnd()), true);
                long gapFrom = -1, gapTo = -1;
                while (it.hasNext()) {
                    CodeUnit cu = it.next();
                    Address a = cu.getMinAddress();
                    boolean undefined = cu instanceof Data && !((Data) cu).isDefined();
                    if (undefined && !named(a)) {
                        if (gapFrom < 0) gapFrom = a.getOffset();
                        gapTo = cu.getMaxAddress().getOffset();
                        continue;
                    }
                    if (gapFrom >= 0) { gap(gapFrom, gapTo); gapFrom = -1; }
                    head(a);
                    if (undefined) {
                        gapFrom = a.getOffset();
                        gapTo = cu.getMaxAddress().getOffset();
                    } else if (cu instanceof Instruction) {
                        inner(cu);
                        instructions++;
                        out.println(String.format("%08x  %-20s  %s%s%s", a.getOffset(), hex(cu.getBytes(), 10),
                            rendered((Instruction) cu), portNote(cu),
                            suspects.contains(a.getOffset()) ? SUSPECT : ""));
                    } else {
                        inner(cu);
                        data((Data) cu);
                    }
                }
                if (gapFrom >= 0) gap(gapFrom, gapTo);
            }
        }
        if (instructions == 0) throw new IllegalStateException("no instruction listed for " + prog);
        println("listed " + prog + " -> " + outFile);
    }
}
