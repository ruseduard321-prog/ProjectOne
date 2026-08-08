"""The workflow engine: definitions, steps, agents and the runner that sequences them.

A package rather than a module because [[Agent Architecture]] requires agents to
be addable and replaceable without touching the engine, and that separation is
only real if they live in different files.

    models.py       the vocabulary, the step contract, definitions
    agents.py       agent implementations, each one step
    definitions.py  the registry of workflows this deployment can run
    runner.py       execution, persistence and the approval gate
"""
