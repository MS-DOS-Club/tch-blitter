// DumpFuncs.java -- decompiles SPECIFIC functions of an analysed program, by address, without
// re-analysing the project: for each address in DECOMP_ADDRS (hex, comma-separated) it prints the
// function containing it, its pseudo-C between @@C_START/@@C_END and up to 250 of its instructions
// between @@ASM_START/@@ASM_END, each with the call and jump targets it references.
//
// Usage: DECOMP_ADDRS=e0646,e2dfe analyzeHeadless <proj> tch -process <img.bin> -noanalysis \
//          -scriptPath scripts/ghidra -postScript DumpFuncs.java
// disasm/README.md has the full command line.
//@category TCH

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.app.decompiler.*;
import ghidra.program.model.symbol.Reference;

public class DumpFuncs extends GhidraScript {
    public void run() throws Exception {
        String env = System.getenv("DECOMP_ADDRS");
        if (env == null || env.isEmpty()) env = "e0646";
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Listing lst = currentProgram.getListing();
        for (String s : env.split(",")) {
            long a = Long.parseLong(s.trim(), 16);
            Function f = getFunctionContaining(toAddr(a));
            println("@@@@ " + Long.toHexString(a)
                + (f!=null? "  "+f.getName()+"  entry="+f.getEntryPoint()+" size="+f.getBody().getNumAddresses():"  (no func)"));
            if (f == null) continue;
            DecompileResults r = di.decompileFunction(f, 120, monitor);
            String c = (r!=null && r.decompileCompleted()) ? r.getDecompiledFunction().getC() : null;
            println("@@C_START"); if (c!=null) println(c); else println("(no C)"); println("@@C_END");
            println("@@ASM_START");
            InstructionIterator it = lst.getInstructions(f.getBody(), true);
            int n=0;
            while (it.hasNext() && n<250) {
                Instruction ins = it.next();
                String ref = "";
                for (Reference rr : ins.getReferencesFrom())
                    if (rr.getToAddress()!=null && rr.getReferenceType().isCall() || rr.getReferenceType().isJump())
                        ref += " ->"+rr.getToAddress();
                println("A|"+ins.getAddress()+"|  "+ins.toString()+ref);
                n++;
            }
            println("@@ASM_END");
        }
    }
}
