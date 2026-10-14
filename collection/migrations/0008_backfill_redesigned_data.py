from django.db import migrations


def backfill_data(apps, schema_editor):
    ConsentRecord = apps.get_model('collection', 'ConsentRecord')
    ParticipantIdentity = apps.get_model('collection', 'ParticipantIdentity')
    GuardianConsent = apps.get_model('collection', 'GuardianConsent')
    MediaCapture = apps.get_model('collection', 'MediaCapture')

    for consent in ConsentRecord.objects.all():
        if not ParticipantIdentity.objects.filter(session=consent.session).exists():
            candidate_id = consent.patient_id or f"PID-{str(consent.session.session_id)[:8].upper()}"
            if ParticipantIdentity.objects.filter(patient_id=candidate_id).exists():
                candidate_id = f"{candidate_id}-{str(consent.session.session_id)[:8].upper()}"
            ParticipantIdentity.objects.create(
                session=consent.session,
                patient_id=candidate_id,
                participant_email=consent.participant_email,
                ip_address=consent.ip_address,
                user_agent=consent.user_agent,
                created_at=consent.created_at,
            )

        if consent.is_minor and (consent.guardian_name or consent.guardian_contact):
            if not GuardianConsent.objects.filter(consent=consent).exists():
                GuardianConsent.objects.create(
                    consent=consent,
                    guardian_name=consent.guardian_name,
                    guardian_relationship=consent.guardian_relationship,
                    guardian_contact=consent.guardian_contact,
                    confirm_parent=consent.guardian_confirm_parent,
                    confirm_minor=consent.guardian_confirm_minor,
                    confirm_modalities=consent.guardian_confirm_modalities,
                    confirm_terms=consent.guardian_confirm_terms,
                    created_at=consent.created_at,
                )

    for capture in MediaCapture.objects.all():
        if isinstance(capture.metadata, dict):
            updated = False
            if not capture.sound_code and capture.metadata.get("sound_id"):
                capture.sound_code = str(capture.metadata.get("sound_id"))
                updated = True
            if capture.duration_seconds is None and capture.metadata.get("duration_seconds"):
                try:
                    capture.duration_seconds = float(capture.metadata.get("duration_seconds"))
                    updated = True
                except (ValueError, TypeError):
                    pass
            if capture.hold_ms is None and capture.metadata.get("hold_ms"):
                try:
                    capture.hold_ms = int(capture.metadata.get("hold_ms"))
                    updated = True
                except (ValueError, TypeError):
                    pass
            if updated:
                capture.save()


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0007_analysisresultcapture_guardianconsent_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_data, migrations.RunPython.noop),
    ]
