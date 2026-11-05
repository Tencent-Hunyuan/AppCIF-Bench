import sys
import math
try:
    from .spatiotemporal_trade_optimizer import PsychedelicCity
    from .event_catalog import EVENTS_DB
except ImportError:
    from spatiotemporal_trade_optimizer import PsychedelicCity
    from event_catalog import EVENTS_DB

def format_path(start, end, path_segments=None):
    # Helper to format coordinates
    return f"{start} -> {end}"

def run_solver(current_k, current_pos_str, event_name):
    # Parse pos
    try:
        current_pos = tuple(map(int, current_pos_str.strip('()').split(',')))
    except:
        print("Invalid position format. Use (x,y,z)")
        return

    # Find event
    event_info = None
    for k, v in EVENTS_DB.items():
        if k in event_name:
            event_info = v
            break
            
    if not event_info and event_name != "None":
        print(f"Warning: Event '{event_name}' not found in DB.")
        # Proceed with empty event list if not found?
        # Or maybe the user meant no event.
        events_list = []
    else:
        # Construct event object for the engine
        # Engine expects list of dicts with 'start_k'
        if event_info:
            # Assume event started "recently" or is active now.
            # Prompt says "Given occurring event".
            # We assume it started at current_k or slightly before.
            # Let's set start_k = current_k for simplicity, so it is active.
            e = event_info.copy()
            e['start_k'] = current_k
            events_list = [e]
        else:
            events_list = []

    # Initialize Engine
    city = PsychedelicCity(current_k, current_pos, events_list)
    
    # Run Optimization
    plan = city.optimize()
    
    if not plan:
        print("No profitable trade found within constraints.")
        return

    # Output Result
    print("\n=== Optimal Trade Plan ===")
    print(f"Current State: k={current_k}, Pos={current_pos}")
    print(f"Event: {event_name}")
    print("-" * 30)
    print(f"Target Item: {plan['item']}")
    print(f"1. Wait {plan['w1']} Xun (at start)")
    
    buy_k = plan['buy_k']
    jump = plan['jump']
    
    print(f"2. Move to {jump['type']}{jump['id']} (Pos: {jump['pos_before']})")
    print(f"   - Arrival at k={jump['arrival_k']}")
    print(f"   - Fuel: {jump['fuel_to_jump']}")
    
    print(f"3. Jump through {jump['type']}{jump['id']}")
    print(f"   - Tax: {plan['tax']}")
    if jump['dk'] != 0:
        print(f"   - Time Leap: {jump['dk']} Xun")
        
    print(f"4. Move to {plan['item']} Destination")
    print(f"   - Sell Arrival at k={plan['sell_k'] - plan['w2']}")
    
    if plan['w2'] > 0:
        print(f"5. Wait {plan['w2']} Xun at destination")
        
    print(f"6. Sell at k={plan['sell_k']}")
    print(f"   - Buy Price Level: {plan['buy_lvl']}")
    print(f"   - Sell Price Level: {plan['sell_lvl']}")
    
    print("-" * 30)
    print(f"Total Profit: {plan['profit']}")
    print(f"Total Fuel: {plan['fuel']}")
    print(f"Total Tax: {plan['tax']}")

if __name__ == "__main__":
    # Example usage
    # python solution_formatter.py 0 "(0,0,0)" "霓虹胃袋"
    
    if len(sys.argv) > 3:
        run_solver(int(sys.argv[1]), sys.argv[2], sys.argv[3])
    else:
        # Default Test
        run_solver(0, "(0,0,0)", "霓虹胃袋")
