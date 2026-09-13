import { useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text } from 'react-native';
import { useRouter } from 'expo-router';

import { createProperty } from '@/api/properties';
import { ApiRequestError } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';

export default function NewPropertyScreen() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [country, setCountry] = useState('Nigeria');
  const [description, setDescription] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    if (!name.trim() || !address.trim() || !city.trim() || !state.trim()) {
      setError('Name, address, city and state are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createProperty({
        name: name.trim(),
        property_type: propertyType.trim() || 'APARTMENT',
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        country: country.trim() || 'Nigeria',
        description: description.trim(),
        currency: currency.trim() || 'NGN',
      });
      router.replace(`/(app)/properties/property-detail?id=${created.id}`);
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to create property.';
      setError(msg);
      Alert.alert('Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="New Property">
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <TextField label="Name *" value={name} onChangeText={setName} placeholder="Sunset Apartments" />
      <TextField
        label="Property type"
        value={propertyType}
        onChangeText={setPropertyType}
        placeholder="APARTMENT (default)"
      />
      <TextField label="Address *" value={address} onChangeText={setAddress} />
      <TextField label="City *" value={city} onChangeText={setCity} />
      <TextField label="State *" value={state} onChangeText={setState} />
      <TextField label="Country" value={country} onChangeText={setCountry} />
      <TextField label="Currency" value={currency} onChangeText={setCurrency} />
      <TextField
        label="Description"
        value={description}
        onChangeText={setDescription}
        multiline
      />
      <Button title="Create property" onPress={onSubmit} loading={saving} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  error: {
    color: '#d32f2f',
    fontSize: 14,
  },
});