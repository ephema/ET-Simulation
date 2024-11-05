from inspect import _empty
from utils import *
import heapq
import math
from models import *

#### Util functions 

### Pricing Mechanisms 

## First price auction

def purchase_tickets_first_price(previous_state, tickets_available, ticket_holder, ticket_price, total_MEV_captured_by_protocol, params):
    updated_ticket_price = ticket_price
    updated_MEV_captured_by_protocol = total_MEV_captured_by_protocol 
    
    while tickets_available:
        bids = [(holder, holder.decide_bid_first_price(params)) for holder in ticket_holder]
        if bids:
            # Find the highest bid
            max_bid = max(bids, key=lambda x: x[1])
            holder = max_bid[0]
            # Assign only one ticket to the highest bidder
            bought_ticket = tickets_available.pop(0)
            assign_ticket_to_holder(max_bid[1], holder, bought_ticket)
            # Update the ticket price to the highest bid
            updated_ticket_price = max_bid[1]
            updated_MEV_captured_by_protocol += updated_ticket_price
            print(f"Highest Bid in First price auction: {max_bid[1]:.2f}. Current total MEV captured: {updated_MEV_captured_by_protocol:.2f}") # Debug print
        else: 
            break # No more bids

    return updated_ticket_price, updated_MEV_captured_by_protocol

## Second price auction

def purchase_tickets_second_price(previous_state, tickets_available, ticket_holder, ticket_price, total_MEV_captured_by_protocol, params):
    updated_ticket_price = ticket_price
    updated_MEV_captured_by_protocol = total_MEV_captured_by_protocol 
    while tickets_available:
        bids = [(holder, holder.decide_bid_second_price(params, previous_state=previous_state)) for holder in ticket_holder]
        if len(bids) >= 2:
            # Find the highest two bid
            max_bid, second_max_bid = heapq.nlargest(2, bids, key=lambda x: x[1])
            holder = max_bid[0]
            # Assign only one ticket to the highest bidder
            bought_ticket = tickets_available.pop(0)
            assign_ticket_to_holder(second_max_bid[1], holder, bought_ticket)
            # Update the ticket price to the highest bid
            updated_ticket_price = second_max_bid[1]
            updated_MEV_captured_by_protocol += updated_ticket_price
            print(f"Highest Bid in Second price auction by {holder.id}: {max_bid[1]:.2f}. Current total MEV captured: {updated_MEV_captured_by_protocol:.2f}") # Debug print
        
        elif len(bids) == 1:
            # If only one bid is available, price will be "1"
            max_bid = bids[0]
            holder = max_bid[0]
            bought_ticket = tickets_available.pop(0)
            assign_ticket_to_holder(1, holder, bought_ticket)
            updated_ticket_price = 1
            updated_MEV_captured_by_protocol += updated_ticket_price
            print(f"Only one bidder. Assigned at price 1. Current total MEV captured: {updated_MEV_captured_by_protocol:.2f}")
        else:
            break

    return updated_ticket_price, updated_MEV_captured_by_protocol

## EIP-1559 Style pricing
 
def purchase_tickets_EIP_1559(previous_state, tickets_available, ticket_holder, ticket_price, total_MEV_captured_by_protocol, tickets, params):
    
    # Randomize the order of ticket holders to assume that latency is distributed randomly (deciding potentially about buying order)
    randomized_ticket_holder = ticket_holder
    random.shuffle(randomized_ticket_holder)
    
    # Adjust ticket price once to account for redeemed ticket
    new_ticket_price = adjust_ticket_price_1559(ticket_price, ticket_holder, tickets, params)
    # Prepare the queue of holders and the number of tickets they can potentially buy
    holders_queue = []
    for holder in randomized_ticket_holder:
        if holder.available_funds >= new_ticket_price:
            if holder.decide_EIP_1559_ticket(ticket_price, params):
                max_tickets = min(holder.available_funds // new_ticket_price, len(tickets_available))
                holders_queue.append([holder, max_tickets])
    
    # Flag to check if at least one ticket was purchased in the last full cycle
    tickets_purchased = True
    counter = 0
    
    while tickets_available and tickets_purchased and counter < params['EIP-1559_max_tickets']:
        tickets_purchased = False  # Reset the flag at the start of the cycle
       
        # Iterate over each holder to attempt ticket purchases
        for holder_data in holders_queue:
            holder, max_tickets = holder_data
            if max_tickets > 0:
                if counter == params['EIP-1559_max_tickets']:
                    break
                
                # Assign ticket and update holder data
                ticket = tickets_available.pop(0)
                assign_ticket_to_holder(new_ticket_price, holder, ticket)
                holder_data[1] -= 1  # Decrement the tickets this holder can still buy
                tickets_purchased = True  # Set flag as successful purchase made
                total_MEV_captured_by_protocol += new_ticket_price
                counter += 1
                # Re-evaluate the maximum number of tickets this holder can buy
                holder_data[1] = min(holder.available_funds // new_ticket_price, len(tickets_available))
    
                if not tickets_available:  # Exit if no tickets are left
                    break
    
        # Remove holders who can no longer buy tickets
        holders_queue = [hd for hd in holders_queue if hd[1] > 0 and hd[0].available_funds >= new_ticket_price]
    
    if not tickets_available:
        print("All tickets sold.")

    elif counter == params['EIP-1559_max_tickets']:
        print(f"All {params['EIP-1559_max_tickets']} tickets have been sold in this slot.")
    elif not any(hd[1] > 0 for hd in holders_queue):
        print("No more buyers want or can afford tickets at the current price.")
    
    # Adjust the ticket price
    new_ticket_price = adjust_ticket_price_1559(new_ticket_price, ticket_holder, tickets, params)

    return new_ticket_price, total_MEV_captured_by_protocol

def adjust_ticket_price_1559(ticket_price, ticket_holder, tickets, params):
    # Double Check
    new_ticket_price = ticket_price
    if params['selling_mechanism'] == 'EIP-1559':
        total_tickets_held = sum(1 for ticket in tickets if ticket.holder_id is not None and ticket.redeemed is False)
        print(f"Total Tickets held: {total_tickets_held}")
        target_tickets = params['max_tickets']/2
        new_ticket_price = ticket_price*(1 + 1/params['EIP-1559_adjust_factor'] * ((total_tickets_held - target_tickets) / target_tickets))
        percentage_change = (new_ticket_price - ticket_price)/ticket_price *100
        print(f"Adjusted Ticket Price: {new_ticket_price:.2f} from {ticket_price:.2f} ({percentage_change:.2f} %)")

    return new_ticket_price

def purchase_tickets_AMM(ticket_holder, ticket_price, total_MEV_captured_by_protocol, tickets, params, previous_state=None):

    print("-- Opening AMM Ticket Buying (& Selling) Round --")
    ticket_purchased_or_sold = True
    # Adjust ticket price once to account for redeemed ticket
    new_ticket_price = adjust_ticket_price_AMM(ticket_price, ticket_holder, tickets, params) 
    # Market opens
    while ticket_purchased_or_sold:
        ticket_purchased_or_sold = False
        random.shuffle(ticket_holder) # We assume same latency so who can buy the ticket first is random, but each holder can only buy one ticket per round
        total_tickets_held = sum(1 for ticket in tickets if ticket.holder_id is not None and not ticket.redeemed)
        for holder in ticket_holder:
            if holder.available_funds >= new_ticket_price:
                if holder.decide_AMM_ticket(new_ticket_price, params):
                    highest_id = max(tickets, key=lambda ticket: ticket.id).id

                    # If reimbursable tickets might not need to be created new, otherwise create new ticket and append
                    
                    if params['reimbursement_factor'] is not None:
                        new_ticket = None
                        for ticket in tickets:
                            if ticket.holder_id is None:
                                new_ticket = ticket
                                break
                        if new_ticket is None: 
                            new_ticket = Ticket(highest_id + 1, params, previous_state)
                            tickets.append(new_ticket)
                            print(f"New Ticket created in AMM as no ticket avail: {new_ticket.id}")
                    else:
                        new_ticket = Ticket(highest_id + 1, params, previous_state)
                        print(f"New Ticket created in AMM as no ticket avail: {new_ticket.id}")
                        tickets.append(new_ticket)
                    
                    assign_ticket_to_holder(new_ticket_price, holder, new_ticket)
                    total_MEV_captured_by_protocol += new_ticket_price
                    ticket_purchased_or_sold = True
                    new_ticket_price = adjust_ticket_price_AMM(new_ticket_price, ticket_holder, tickets, params) # As dynamic market tickets will update after every step
            # Only relevant if reimbursable tickets are enabled
            if params['reimbursement_factor'] is not None:
                if holder.holder_decide_AMM_sell(tickets, new_ticket_price, params):
                    # Identify first ticket by this holder
                    for ticket in tickets:
                        if ticket.holder_id == holder.id:
                            discounted_ticket_price = new_ticket_price * (1 - params['reimbursement_factor'])
                            unassign_ticket_from_holder(discounted_ticket_price, holder, ticket)
                            total_MEV_captured_by_protocol -= discounted_ticket_price
                            ticket_purchased_or_sold = True
                            new_ticket_price = adjust_ticket_price_AMM(new_ticket_price, ticket_holder, tickets, params)
                            print(f"Holder {holder.id} sold ID {ticket.id}. New price ticket price {new_ticket_price}")
                            break
                
    ticket_holder.sort(key=lambda x: x.id)
    total_tickets_held = sum(1 for ticket in tickets if ticket.holder_id is not None and not ticket.redeemed)

    print(f"-- Closing of AMM ticket purchasing round. Total tickets held:{total_tickets_held}. --")

    return new_ticket_price, total_MEV_captured_by_protocol


def adjust_ticket_price_AMM(ticket_price, ticket_holder, tickets, params):
    
    new_ticket_price = ticket_price
    if params['selling_mechanism'] == 'AMM-style':
        total_tickets_held = sum(1 for ticket in tickets if ticket.holder_id is not None and ticket.redeemed is False)
        print(f"Total Tickets held: {total_tickets_held}")
        target_tickets_held = params['max_tickets']/2
        target_tickets_issued = 1
        excess_tickets_held = total_tickets_held - target_tickets_held # Note that plus gas_in_block (+1) is not necessary as total_tickets_held is recalculated with the new ticket already issued
        print(f"AMM: Excess Tickets held: {excess_tickets_held}")
        adjust_factor = 1 / params['AMM_adjust_factor']
        b = 6 # Defined for the purose of this simulation to 6, can be adjusted. For details read the research report.
        new_ticket_price = (
                math.exp(b) *
                (math.exp(((excess_tickets_held + 1) / target_tickets_issued) * adjust_factor) 
                        - math.exp(((excess_tickets_held) / target_tickets_issued) * adjust_factor))
        )
        percentage_change = (new_ticket_price - ticket_price)/ticket_price *100
        print(f"Adjusted Ticket Price (AMM): {new_ticket_price:.2f} from {ticket_price:.2f} ({percentage_change:.2f} %)")

    return new_ticket_price

def run_secondary_market_auction(holder, tickets, ticket_holders, current_slot, vola_this_slot, params):
    tickets_this_holder = []
    # Identify all the tickets of this holder
    for ticket in tickets:
        if ticket.holder_id == holder.id and not ticket.redeemed:
            tickets_this_holder.append(ticket)

    # Only proceed if the holder has tickets
    if tickets_this_holder:
        tickets_this_holder.sort(key=lambda x: (x.assigned_slot if x.assigned_slot is not None else float('inf')))
        ticket_for_sale = tickets_this_holder[0]  # for simplicity reasons we assume only the "nearest" ticket can be sold
        #print(f"Debug Print: Ticket For Sale - ID: {ticket_for_sale.id}, Assigned Slot: {ticket_for_sale.assigned_slot}. Exp. Slot: {ticket_for_sale.expiry_slot} Redeemed: {ticket_for_sale.redeemed}. Purch. Price: {ticket_for_sale.price_paid:.2f}")

        # Collect bids
        bids = []
        for th in ticket_holders:
            bid_value = th.decide_bid_second_price(
                params=params,
                ticket_for_sale=ticket_for_sale,
                current_slot=current_slot,
                vola_this_slot=vola_this_slot
                )
            bids.append({'holder': th, 'bid_value': bid_value})

        # Sort bids in descending order by bid value
        bids.sort(key=lambda x: x['bid_value'], reverse=True)

        # Process the winning bid if any bids exist
        if bids:
            winning_bidder = bids[0]['holder']
            winning_bid = bids[1]['bid_value']  # Second Price Auction Rule

            # Check if the ticket holder is willing to sell
            if winning_bidder.id != holder.id:
                assign_ticket_to_holder(winning_bid, winning_bidder, ticket_for_sale) 
                holder.available_funds += winning_bid
                holder.earnings += winning_bid
                holder.sec_m_earnings += winning_bid
                # winning_bidder.earnings -= winning_bid # Currently earnings are calculated as gross earnings
                # holder.costs -= winning_bid # Currently secondary market revenues are not deducted from costs, could be challenged
                print(f"Ticket {ticket_for_sale.id} sold from holder {holder.id} to {winning_bidder.id} for {winning_bid:.3f}")
            else:
                print(f"Holder {holder.id} is not willing to sell the ticket for {winning_bid:.3f}")
        else:
            warning.warn("No valid bids received.")
    else:
        print(f"Holder {holder.id} has no tickets to sell.")

    return tickets, holder