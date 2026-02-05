import sys
from .scenarios import SCENARIOS
from .runner import DemoRunner

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m demo <scenario>")
        print("Available scenarios:")
        for name in SCENARIOS:
            print(f"  - {name}")
        sys.exit(1)
        
    scenario_name = sys.argv[1]
    if scenario_name not in SCENARIOS:
        print(f"Error: Unknown scenario '{scenario_name}'")
        sys.exit(1)
        
    scenario = SCENARIOS[scenario_name]
    
    print(f"Scenario: {scenario.name}")
    print("-" * 32)
    print(f"Description: {scenario.description}")
    print(f"Ring capacity: {scenario.ring_capacity}")
    print(f"Load: ingest={scenario.ingest_ticks_per_step} / execute={scenario.execution_polls_per_step}")
    print("")
    
    runner = DemoRunner()
    summary = runner.run(scenario)
    
    # Calculate lifecycle transitions for clean output
    print("Lifecycle:")
    # Always show step 0
    print(f"  step 0  -> {summary.steps[0].lifecycle_state}")
    
    # Show changes
    current = summary.steps[0].lifecycle_state
    for s in summary.steps:
        if s.lifecycle_state != current:
            print(f"  step {s.step_index} -> {s.lifecycle_state}")
            current = s.lifecycle_state
            
    print("")
    
    # Overruns
    total_overruns = sum(s.overruns for s in summary.steps)
    first_overrun = next((s for s in summary.steps if s.overruns > 0), None)
    
    print("Overruns:")
    if first_overrun:
        print(f"  first_overrun_step: {first_overrun.step_index}")
    else:
        print("  first_overrun_step: None")
    print(f"  total_overruns: {total_overruns}")
    
    print("")
    print("Summary:")
    print(f"  total_ingested: {summary.total_ingested}")
    print(f"  total_acks: {summary.total_acks}")
    print(f"  final_state: {summary.final_state}")

if __name__ == "__main__":
    main()
