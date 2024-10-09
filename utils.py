import random
import copy
from models import Ticket, TicketHolderAgent # self defined in models.py


# Util function for ticket issuance
def ticket_issuance(previous_state, params):
    tickets = copy.deepcopy(previous_state['tickets'])
    if tickets:
        current_ticket_id = max(tickets, key=lambda ticket: ticket.id).id
    else: 
        current_ticket_id = 1
    unredeemed_tickets = [t for t in tickets if not t.redeemed]
    if len(unredeemed_tickets) <= (params['max_tickets']):
        # Calculate how many new tickets to issue
        new_tickets_needed = params['max_tickets'] - len(unredeemed_tickets)
        new_ticket = None
        for _ in range(new_tickets_needed):
            current_ticket_id += 1
            new_ticket = Ticket(current_ticket_id, params, previous_state)
            tickets.append(new_ticket)
        if new_ticket is not None:
            print(f"Issued {new_tickets_needed} new tickets with the last ticket ID {current_ticket_id}. Exp. slot last ticket: {new_ticket.expiry_slot}")
        else:
            print(f"0 new Tickets needed")
        
    return tickets, current_ticket_id

# Util function - randomly shuffles all held tickets and assignes 32 to the slots of the next epoch
def assign_tickets_to_slots(previous_state, params, epoch, tickets):   
    
    random.shuffle(tickets)  # Randomize tickets to distribute slots fairly

    start_slot = epoch * params['slots_per_epoch'] + 1
    end_slot = start_slot + params['slots_per_epoch']
    slot_index = start_slot

    assigned_tickets = []  # To keep track of which tickets were assigned

    for slot in range(start_slot, end_slot + 1):
        if slot not in [ticket.assigned_slot for ticket in tickets]: # check that the slot is not already assigned
            for ticket in tickets:
                if (
                    ticket.holder_id is not None and  # Only sold tickets get assigned (you cannot buy an assigned ticket)
                    not ticket.redeemed and
                    ticket.assigned_slot is None and  
                    (ticket.expiry_slot is None or slot <= ticket.expiry_slot) and # None slots evaluate as true and non-None and second condition
                    ticket not in assigned_tickets
                ):
                    # Assign the ticket to the current slot
                    ticket.assigned_slot = slot
                    ticket.assigned_epoch = epoch
                    ticket.assigned = True
                    assigned_tickets.append(ticket)
                    break 
    
    # Debug prints
    assigned_slots = [ticket.assigned_slot for ticket in tickets if ticket.assigned and not ticket.redeemed]
    print(f"Number of Assigned Tickets to Slots: {len(assigned_tickets)}. Assigned slots: {len(assigned_slots)} Starting with slot {slot_index} and end slot {end_slot}")
    unassigned_slots = set(range(slot_index, end_slot + 1)) - set(assigned_slots)
    if unassigned_slots:
        print(f"Unassigned Slots: {sorted(unassigned_slots)}")
    
    return tickets

# Function to assign a single ticket (needed if only a few expiring tickets are always issued)
def assign_ticket_to_slot(previous_state, params, epoch, tickets, slot):   
    random.shuffle(tickets)  # Randomize tickets to distribute slots fairly
    assigned_ticket = None
    for ticket in tickets:
            if (
                ticket.holder_id is not None and  # Only sold tickets get assigned (you cannot buy an assigned ticket)
                not ticket.redeemed and
                ticket.assigned_slot is None and  
                (ticket.expiry_slot is None or slot <= ticket.expiry_slot) # None slots evaluate as true and non-None and second conditions
            ):
                # Assign the ticket to the current slot
                ticket.assigned_slot = slot
                ticket.assigned_epoch = epoch
                ticket.assigned = True
                assigned_ticket = ticket
                break
            # Special Case for JIT auctions, ticket needs to be assigned
            elif (params['max_tickets'] == 1 and
                    not ticket.redeemed and
                    ticket.assigned_slot is None and  
                    (ticket.expiry_slot is None or slot <= ticket.expiry_slot)
                  
            ):
                ticket.assigned_slot = slot
                ticket.assigned_epoch = epoch
                ticket.assigned = True
                assigned_ticket = ticket
                break

    
    # Debug prints
    if assigned_ticket:
        print(f"A single ticket with ID {assigned_ticket.id} has been assigned to slot {slot}.")
    else:
        # print(f"No tickets available to allocate to slot {slot}")
        pass
    return tickets
    

# Util method - assign tickets to holders for initialization or after purchase or trade
def assign_ticket_to_holder(ticket_price, holder, ticket):
    ticket.holder_id = holder.id
    ticket.price_paid = ticket_price
    holder.available_funds -= ticket_price
    holder.costs += ticket_price
    if (holder.available_funds < 0):
        print(f"WARNING: Holder {holder.id} has a negative Fund balance of {holder.available_funds}")
    print(f"Ticket {ticket.id} assigned to Holder {holder.id} at price {ticket_price:.3f}")

# Util method - unassign tickets from holders after refund or trade
def unassign_ticket_from_holder(ticket_price, holder, ticket):
    ticket.holder_id = None
    ticket.price_paid = ticket_price
    holder.available_funds += ticket_price
    holder.costs -= ticket_price
    if (holder.available_funds < 0):
        print(f"WARNING: Holder {holder.id} has a negative Fund balance of {holder.available_funds}")
    print(f"Ticket {ticket.id} unassigned from Holder {holder.id} at price {ticket_price:.3f}")