import random

class Ticket:
    def __init__(self, id):
        self.id = id
        self.assigned = False
        self.holder_id = None
        self.assigned_slot = None
        self.assigned_epoch = None
        self.price_paid = 0 
        self.redeemed = False

# Define the TicketHolders as Agents
class TicketHolderAgent:
    def __init__(self, id, funds):
        self.id = id
        self.tickets = []
        self.available_funds = funds
        self.intrinsic_valuation = random.uniform(10, 50)
        self.MEV_capture_rate = random.uniform(0.1, 1.0)
        self.aggressiveness = random.uniform(0.01, 0.3) # to be adjusted later
        self.discount_factor = 1 # to be adjusted later

    def decide_bid_first_price(self): # Needs to include which ticket to buy, slot information etc? All in self?
        """Calculate bid based on intrinsic valuation, funds, and aggressiveness."""
        max_bid = self.intrinsic_valuation * (1 - self.aggressiveness)
        return min(max_bid, self.available_funds)