"""
Patient Deterioration Model - Step 1.3

Implements Markov deterioration model for MCI casualties based on START triage system.
"""

from typing import Optional


class PatientModel:
    """
    Models patient health deterioration over time based on triage level.

    Attributes:
        triage: Triage level (RED/YELLOW/GREEN/BLACK)
        health: Current health state (0.0 = dead, 1.0 = full health)
        time_since_injury: Minutes elapsed since injury
        is_alive: Boolean indicating if patient is alive
        treatment_status: Current treatment state (WAITING/ENROUTE/DELIVERED)
    """

    def __init__(self, triage_level: str):
        """
        Initialize a patient with given triage level.

        Args:
            triage_level: One of 'RED', 'YELLOW', 'GREEN', 'BLACK'
        """
        self.triage = triage_level.upper()
        self.time_since_injury = 0.0
        self.treatment_status = 'WAITING'

        # Initialize health based on triage
        if self.triage == 'BLACK':
            self.health = 0.0
            self.is_alive = False
        else:
            self.health = 1.0
            self.is_alive = True

    def update(self, delta_time_minutes: float) -> None:
        """
        Update patient health based on time elapsed and current state.

        Deterioration rates (per minute):
        - RED (WAITING): -5% per minute
        - RED (ENROUTE): -2% per minute (ambulance care slows deterioration)
        - YELLOW (WAITING): -0.2% per minute (1% per 5 minutes)
        - YELLOW (ENROUTE): -0.1% per minute (0.5% per 5 minutes)
        - GREEN: No deterioration
        - BLACK: Already deceased

        Args:
            delta_time_minutes: Time increment in minutes
        """
        if not self.is_alive:
            return

        # Update time tracker
        self.time_since_injury += delta_time_minutes

        # Hospital delivery stops deterioration
        if self.treatment_status == 'DELIVERED':
            return

        # Calculate health decrease based on triage and treatment status
        if self.triage == 'RED':
            if self.treatment_status == 'WAITING':
                self.health -= 0.05 * delta_time_minutes  # 5% per minute
            elif self.treatment_status == 'ENROUTE':
                self.health -= 0.02 * delta_time_minutes  # 2% per minute (ambulance care)

        elif self.triage == 'YELLOW':
            if self.treatment_status == 'WAITING':
                self.health -= 0.002 * delta_time_minutes  # 0.2% per minute (1% per 5 min)
            elif self.treatment_status == 'ENROUTE':
                self.health -= 0.001 * delta_time_minutes  # 0.1% per minute (0.5% per 5 min)

            # YELLOW deteriorates to RED if health drops below 0.5
            if self.health < 0.5:
                self.triage = 'RED'

        elif self.triage == 'GREEN':
            # GREEN patients are stable, no deterioration
            pass

        elif self.triage == 'BLACK':
            # Already deceased
            self.is_alive = False
            self.health = 0.0

        # Check for death
        if self.health <= 0.0:
            self.health = 0.0
            self.is_alive = False

    def apply_treatment(self, treatment_type: str) -> None:
        """
        Apply treatment to patient, changing deterioration rate.

        Args:
            treatment_type: Type of treatment
                - 'PICKUP': Patient picked up by ambulance (reduces deterioration)
                - 'HOSPITAL': Patient delivered to hospital (stops deterioration)
        """
        if treatment_type == 'PICKUP':
            self.treatment_status = 'ENROUTE'
        elif treatment_type == 'HOSPITAL':
            self.treatment_status = 'DELIVERED'

    def get_survival_probability(
        self,
        time_to_hospital: float,
        hospital_trauma_level: int
    ) -> float:
        """
        Calculate probability of survival based on current state and hospital delivery.

        Args:
            time_to_hospital: Estimated time to hospital delivery in minutes
            hospital_trauma_level: Hospital trauma level (1=Level I, 2=Level II, etc.)

        Returns:
            Survival probability clamped to [0.0, 1.0]
        """
        # Base survival probability by triage level
        base_survival = {
            'RED': 0.7,
            'YELLOW': 0.9,
            'GREEN': 0.98,
            'BLACK': 0.0
        }

        probability = base_survival.get(self.triage, 0.5)

        # Penalty for exceeding golden hour (60 minutes)
        if time_to_hospital > 60:
            probability -= 0.1

            # Additional penalty for every 30 minutes beyond golden hour
            extra_time = time_to_hospital - 60
            additional_penalties = int(extra_time / 30)
            probability -= 0.05 * additional_penalties

        # Bonus for appropriate trauma center match
        if self.triage in ['RED', 'YELLOW'] and hospital_trauma_level in [1, 2]:
            probability += 0.1

        # Clamp to valid probability range
        return max(0.0, min(1.0, probability))

    def get_state(self) -> dict:
        """
        Get current patient state as dictionary.

        Returns:
            Dictionary with patient state information
        """
        return {
            'triage': self.triage,
            'health': self.health,
            'time_since_injury': self.time_since_injury,
            'is_alive': self.is_alive,
            'treatment_status': self.treatment_status
        }


if __name__ == '__main__':
    # Test patient deterioration model
    print("Testing Patient Deterioration Model...")
    print("=" * 60)

    # Test 1: RED patient without pickup (should die in ~20 minutes)
    print("\n1. Testing RED patient without pickup...")
    red_patient = PatientModel('RED')
    print(f"   Initial state: health={red_patient.health:.2f}, alive={red_patient.is_alive}")

    for minute in range(1, 61):
        red_patient.update(1)
        if minute in [5, 10, 15, 20, 25, 30]:
            print(f"   Minute {minute:2d}: health={red_patient.health:.2f}, alive={red_patient.is_alive}")

    if not red_patient.is_alive and red_patient.time_since_injury <= 25:
        print("   ✓ PASS: RED patient died within ~20 minutes")
    else:
        print("   ✗ FAIL: RED patient did not die as expected")

    # Test 2: RED patient with ambulance pickup
    print("\n2. Testing RED patient with ambulance pickup at 5 minutes...")
    red_patient_pickup = PatientModel('RED')

    # Wait 5 minutes
    red_patient_pickup.update(5)
    print(f"   Before pickup (5 min): health={red_patient_pickup.health:.2f}")

    # Ambulance pickup
    red_patient_pickup.apply_treatment('PICKUP')
    print(f"   Status after pickup: {red_patient_pickup.treatment_status}")

    # Continue for 20 more minutes
    red_patient_pickup.update(20)
    print(f"   After 20 min enroute (25 min total): health={red_patient_pickup.health:.2f}, alive={red_patient_pickup.is_alive}")

    if red_patient_pickup.is_alive and red_patient_pickup.health > 0.3:
        print("   ✓ PASS: Ambulance pickup slowed deterioration")
    else:
        print("   ✗ FAIL: Ambulance did not slow deterioration enough")

    # Test 3: YELLOW patient deteriorating to RED
    print("\n3. Testing YELLOW patient deterioration to RED...")
    yellow_patient = PatientModel('YELLOW')
    print(f"   Initial: triage={yellow_patient.triage}, health={yellow_patient.health:.2f}")

    # Simulate ~250 minutes (should deteriorate to RED around health < 0.5)
    for minute in range(250):
        yellow_patient.update(1)
        if yellow_patient.triage == 'RED':
            print(f"   Deteriorated to RED at minute {minute+1}, health={yellow_patient.health:.2f}")
            break

    if yellow_patient.triage == 'RED':
        print("   ✓ PASS: YELLOW patient deteriorated to RED")
    else:
        print("   ✗ FAIL: YELLOW patient did not deteriorate to RED")

    # Test 4: GREEN patient stability
    print("\n4. Testing GREEN patient (should remain stable)...")
    green_patient = PatientModel('GREEN')
    green_patient.update(60)
    print(f"   After 60 minutes: health={green_patient.health:.2f}, alive={green_patient.is_alive}")

    if green_patient.is_alive and green_patient.health == 1.0:
        print("   ✓ PASS: GREEN patient remained stable")
    else:
        print("   ✗ FAIL: GREEN patient deteriorated unexpectedly")

    # Test 5: Hospital delivery stops deterioration
    print("\n5. Testing hospital delivery...")
    red_patient_hospital = PatientModel('RED')
    red_patient_hospital.update(5)
    health_before = red_patient_hospital.health

    red_patient_hospital.apply_treatment('HOSPITAL')
    red_patient_hospital.update(10)

    print(f"   Health before hospital: {health_before:.2f}")
    print(f"   Health after 10 min at hospital: {red_patient_hospital.health:.2f}")

    if red_patient_hospital.health == health_before:
        print("   ✓ PASS: Hospital delivery stopped deterioration")
    else:
        print("   ✗ FAIL: Deterioration continued at hospital")

    # Test 6: Survival probability calculation
    print("\n6. Testing survival probability calculation...")

    # RED patient, quick transport to Level I hospital
    red_fast = PatientModel('RED')
    prob1 = red_fast.get_survival_probability(time_to_hospital=30, hospital_trauma_level=1)
    print(f"   RED, 30 min to Level I: {prob1:.2f} (expected ~0.8)")

    # RED patient, slow transport, no trauma center
    red_slow = PatientModel('RED')
    prob2 = red_slow.get_survival_probability(time_to_hospital=90, hospital_trauma_level=5)
    print(f"   RED, 90 min to Level V: {prob2:.2f} (expected ~0.55)")

    # YELLOW patient, quick transport
    yellow = PatientModel('YELLOW')
    prob3 = yellow.get_survival_probability(time_to_hospital=45, hospital_trauma_level=2)
    print(f"   YELLOW, 45 min to Level II: {prob3:.2f} (expected ~1.0)")

    if 0.75 <= prob1 <= 0.85 and 0.50 <= prob2 <= 0.60 and prob3 >= 0.95:
        print("   ✓ PASS: Survival probabilities calculated correctly")
    else:
        print("   ✗ FAIL: Survival probability calculation incorrect")

    # Test 7: BLACK patient
    print("\n7. Testing BLACK patient...")
    black_patient = PatientModel('BLACK')
    print(f"   BLACK patient: health={black_patient.health:.2f}, alive={black_patient.is_alive}")

    if not black_patient.is_alive and black_patient.health == 0.0:
        print("   ✓ PASS: BLACK patient correctly marked as deceased")
    else:
        print("   ✗ FAIL: BLACK patient state incorrect")

    print("\n" + "=" * 60)
    print("✓ All patient deterioration tests completed!")
