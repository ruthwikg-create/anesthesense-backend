"""Compatibility CLI for the unified AnestheSense inference pipeline."""
from agent import evaluate_patient_risk
from schema import PatientTelemetry

TEST_TELEMETRY=PatientTelemetry(patient_id="PATIENT-001",telemetry=[
{"minute":-5,"MAP":76,"HR":72,"SVV":8,"EtCO2":35},{"minute":-4,"MAP":73,"HR":70,"SVV":8,"EtCO2":35},
{"minute":-3,"MAP":70,"HR":68,"SVV":9,"EtCO2":34},{"minute":-2,"MAP":67,"HR":65,"SVV":9,"EtCO2":34},
{"minute":-1,"MAP":65,"HR":63,"SVV":9,"EtCO2":34},{"minute":0,"MAP":63,"HR":62,"SVV":8,"EtCO2":33}])
if __name__=="__main__": print(evaluate_patient_risk(TEST_TELEMETRY).model_dump_json(indent=2))
