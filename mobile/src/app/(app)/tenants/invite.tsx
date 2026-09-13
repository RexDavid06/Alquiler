import { useCallback, useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Picker } from '@react-native-picker/picker';

import { createInvitation } from '@/api/tenants';
import { listProperties, listUnits } from '@/api/properties';
import { ApiRequestError } from '@/api/client';
import type { Property, Unit } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';
import { useTheme } from '@/hooks/use-theme';

export default function InviteTenantScreen() {
  const router = useRouter();
  const theme = useTheme();

  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');

  const [properties, setProperties] = useState<Property[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [propertyId, setPropertyId] = useState<number | ''>('');
  const [unitId, setUnitId] = useState<number | ''>('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listProperties()
      .then((res) => setProperties(res.results))
      .catch(() => setProperties([]));
  }, []);

  useEffect(() => {
    setUnitId('');
    setUnits([]);
    if (propertyId === '') return;
    void listUnits(propertyId)
      .then((res) => {
        setUnits(res.results);
        setUnitId(res.results[0]?.id ?? '');
      })
      .catch(() => setUnits([]));
  }, [propertyId]);

  const onSubmit = async () => {
    if (!email.trim()) {
      setError('Email is required.');
      return;
    }
    if (propertyId === '' || unitId === '') {
      setError('Select a property and unit for this tenant.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createInvitation({
        email: email.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        property: propertyId,
        unit: unitId,
      });
      Alert.alert('Invitation sent', 'The tenant will receive an email invitation to sign up.', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to send invitation.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="Invite Tenant">
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TextField
        label="Email *"
        value={email}
        onChangeText={setEmail}
        placeholder="tenent@example.com"
        keyboardType="email-address"
      />
      <TextField label="First name" value={firstName} onChangeText={setFirstName} autoCapitalize="words" />
      <TextField label="Last name" value={lastName} onChangeText={setLastName} autoCapitalize="words" />
      <TextField label="Phone" value={phone} onChangeText={setPhone} keyboardType="phone-pad" />

      <View style={styles.field}>
        <Text style={[styles.label, { color: theme.textSecondary }]}>Property *</Text>
        {properties.length === 0 ? (
          <Text style={{ color: theme.textSecondary }}>
            No properties available — create one first.
          </Text>
        ) : (
          <Picker
            selectedValue={propertyId}
            onValueChange={(v) => setPropertyId(v)}
            style={[styles.picker, { color: theme.text }]}
          >
            <Picker.Item label="Select property…" value="" />
            {properties.map((p) => (
              <Picker.Item key={p.id} label={p.name} value={p.id} />
            ))}
          </Picker>
        )}
      </View>

      {propertyId !== '' ? (
        <View style={styles.field}>
          <Text style={[styles.label, { color: theme.textSecondary }]}>Unit *</Text>
          {units.length === 0 ? (
            <Text style={{ color: theme.textSecondary }}>
              This property has no units yet.
            </Text>
          ) : (
            <Picker
              selectedValue={unitId}
              onValueChange={(v) => setUnitId(v)}
              style={[styles.picker, { color: theme.text }]}
            >
              {units.map((u) => (
                <Picker.Item key={u.id} label={u.name} value={u.id} />
              ))}
            </Picker>
          )}
        </View>
      ) : null}

      <Button title="Send invitation" onPress={onSubmit} loading={saving} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  error: { color: '#d32f2f', fontSize: 14 },
  field: { gap: 4 },
  label: { fontSize: 13, fontWeight: '600' },
  picker: { height: 60, fontSize: 16 },
});