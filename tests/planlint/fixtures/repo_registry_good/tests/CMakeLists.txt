# A registry that answers every check target `clean_plan.md` names. It exists so
# that `--source-repo` has a tree the registry lint can be CLEAN against; a run
# in which one lint is always dirty proves nothing about the others.
add_test(NAME t0_alpha COMMAND t0_alpha)
add_test(NAME t0_beta COMMAND t0_beta)
add_test(NAME t0_delta COMMAND t0_delta)
add_test(NAME t0_epsilon COMMAND t0_epsilon)
add_test(NAME t0_eta COMMAND t0_eta)
add_test(NAME t1_gamma COMMAND t1_gamma)
add_test(NAME t2_zeta COMMAND t2_zeta)
