"""rom1.delink - resolved model -> named per-unit target objects.

The delink half of the matching pipeline:

    Model (rom1.model.resolve)
      -> pdb_synth      build/pdb/rom1_named.{yaml,pdb}
      -> data_manifest  build/gen/delink_data_manifest.tsv (+ section manifest)
      -> tool.delinker  vostok-delinker over the retail EXE
      -> run            collect build/objdiff/target-new/<unit>.c.obj

Mechanisms are ported from the proven old tree (scripts/rom1-old/build/);
inputs are adapted to the Model - nothing here re-reads bindings.tsv.
"""
