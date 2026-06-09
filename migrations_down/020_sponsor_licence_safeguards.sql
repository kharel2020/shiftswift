DROP TABLE IF EXISTS compliance_audit_events;
DROP TABLE IF EXISTS sponsor_sms_change_log;
DROP TABLE IF EXISTS sponsor_absence_alerts;
DROP TABLE IF EXISTS sponsored_absence_days;
DROP TABLE IF EXISTS sponsor_working_calendar;
DROP TRIGGER IF EXISTS trg_rtw_immutable ON right_to_work_checks;
DROP FUNCTION IF EXISTS prevent_rtw_mutation();
DROP TABLE IF EXISTS right_to_work_checks;
DROP TABLE IF EXISTS employee_sponsor_profiles;
