// Xref.java -- who references an address: for each address in XREF_ADDRS (hex, comma-separated)
// it prints every reference to it, with the address it comes from, the function holding that
// address and the kind of reference (read, write, call, jump).
//
// Usage: XREF_ADDRS=203510 analyzeHeadless <proj> tch -process <img.bin> -noanalysis \
//          -scriptPath scripts/ghidra -postScript Xref.java
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
public class Xref extends GhidraScript {
    public void run() throws Exception {
        String env = System.getenv("XREF_ADDRS");
        if (env==null||env.isEmpty()) env="203510";
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (String s : env.split(",")) {
            long a = Long.parseLong(s.trim(),16);
            Address addr = toAddr(a);
            println("#### XREFS a "+Long.toHexString(a)+" ####");
            ReferenceIterator it = rm.getReferencesTo(addr);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                println("  from "+r.getFromAddress()+" ("+(f!=null?f.getName():"?")+") "+r.getReferenceType());
            }
        }
    }
}
