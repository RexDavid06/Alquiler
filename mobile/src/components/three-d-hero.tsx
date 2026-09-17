import { useEffect } from 'react';
import { StyleSheet, Text, View, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  SensorType,
  useAnimatedSensor,
  useAnimatedStyle,
  useDerivedValue,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { RADIUS, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const CUBE_SIZE = 132;
const HALF = CUBE_SIZE / 2;
const SCENE_HEIGHT = 300;
const PERSPECTIVE = 1100;

type FaceTransform = NonNullable<ViewStyle['transform']>;

function toTransform(...items: Record<string, number | string | number[]>[]): FaceTransform {
  return items as unknown as FaceTransform;
}

const FACES: { key: string; transform: FaceTransform; accent?: boolean }[] = [
  { key: 'front', transform: toTransform({ translate: [0, 0, HALF] }), accent: true },
  { key: 'back', transform: toTransform({ rotateY: '180deg' }, { translate: [0, 0, HALF] }) },
  { key: 'right', transform: toTransform({ rotateY: '90deg' }, { translate: [0, 0, HALF] }) },
  { key: 'left', transform: toTransform({ rotateY: '-90deg' }, { translate: [0, 0, HALF] }) },
  { key: 'top', transform: toTransform({ rotateX: '90deg' }, { translate: [0, 0, HALF] }) },
  { key: 'bottom', transform: toTransform({ rotateX: '-90deg' }, { translate: [0, 0, HALF] }) },
];

const CHIPS = [
  { label: 'Rent', x: -116, y: -84, z: 64 },
  { label: 'Lease', x: -138, y: 74, z: 44 },
  { label: 'Keys', x: 118, y: -62, z: 104 },
  { label: 'Payments', x: 122, y: 78, z: 84 },
  { label: 'Tenants', x: 2, y: -128, z: 120 },
];

function clamp(value: number) {
  'worklet';
  return Math.max(-1, Math.min(1, value));
}

export function ThreeDHero() {
  const theme = useTheme();
  const gravity = useAnimatedSensor(SensorType.GRAVITY, { interval: 50 });

  const spin = useSharedValue(0);
  const sway = useSharedValue(0);

  useEffect(() => {
    spin.value = withRepeat(
      withTiming(360, { duration: 24000, easing: Easing.linear }),
      -1,
      false,
    );
    sway.value = withRepeat(
      withSequence(
        withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.sin) }),
        withTiming(-1, { duration: 2600, easing: Easing.inOut(Easing.sin) }),
      ),
      -1,
      false,
    );
  }, [spin, sway]);

  const tiltX = useDerivedValue(() => clamp(gravity.sensor.value.y) * -16);
  const tiltY = useDerivedValue(() => clamp(gravity.sensor.value.x) * 16);

  const cubeStyle = useAnimatedStyle(() => ({
    transform: [
      { perspective: PERSPECTIVE },
      { rotateX: `${tiltX.value + 10}deg` },
      { rotateY: `${tiltY.value + spin.value}deg` },
      { rotateZ: `${Math.sin(sway.value * Math.PI) * 3}deg` },
    ],
  }));

  const chipsStyle = useAnimatedStyle(() => ({
    transform: [
      { perspective: PERSPECTIVE },
      { rotateX: `${tiltX.value}deg` },
      { rotateY: `${tiltY.value}deg` },
      { rotateZ: `${Math.sin(sway.value * Math.PI) * 2}deg` },
      { translateY: Math.sin(sway.value * Math.PI) * 6 },
    ],
  }));

  const shadowStyle = useAnimatedStyle(() => ({
    transform: [
      { scaleX: 1 + Math.abs(tiltY.value) / 26 },
      { scaleY: Math.max(0.45, 1 - Math.abs(tiltX.value) / 26) },
    ],
    opacity: 0.9 - Math.abs(tiltX.value) / 60,
  }));

  return (
    <View style={styles.scene} pointerEvents="none">
      <Animated.View style={[styles.platform, cubeStyle]}>
        {FACES.map((face) => (
          <View
            key={face.key}
            style={[
              styles.face,
              {
                borderColor: `${theme.primary}66`,
                backgroundColor: `${theme.primary}1F`,
                transform: face.transform,
              },
            ]}
          >
            <View
              style={[
                styles.badge,
                face.accent
                  ? { backgroundColor: theme.primary, borderColor: theme.primary }
                  : { borderColor: `${theme.primary}55` },
              ]}
            >
              <Text
                style={[
                  styles.badgeText,
                  { color: face.accent ? theme.onPrimary : theme.primary },
                ]}
              >
                A
              </Text>
            </View>
          </View>
        ))}
      </Animated.View>

      <Animated.View style={[styles.chips, chipsStyle]}>
        {CHIPS.map((chip) => (
          <View
            key={chip.label}
            style={[
              styles.chip,
              {
                borderColor: `${theme.primary}44`,
                backgroundColor: theme.background,
                transform: toTransform({ translate: [chip.x, chip.y, chip.z] }),
              },
            ]}
          >
            <View style={[styles.chipDot, { backgroundColor: theme.primary }]} />
            <Text style={[styles.chipText, { color: theme.text }]}>{chip.label}</Text>
          </View>
        ))}
      </Animated.View>

      <Animated.View style={[styles.shadow, shadowStyle]} />
    </View>
  );
}

const styles = StyleSheet.create({
  scene: {
    height: SCENE_HEIGHT,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  platform: {
    width: CUBE_SIZE,
    height: CUBE_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  face: {
    position: 'absolute',
    width: CUBE_SIZE,
    height: CUBE_SIZE,
    borderRadius: RADIUS.large,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    backfaceVisibility: 'hidden',
  },
  badge: {
    width: 42,
    height: 42,
    borderRadius: RADIUS.round,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: 18,
    fontWeight: '800',
  },
  chips: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chip: {
    position: 'absolute',
    left: '50%',
    top: '50%',
    marginTop: -16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: RADIUS.round,
    borderWidth: 1,
    shadowColor: '#000000',
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 3,
  },
  chipDot: {
    width: 6,
    height: 6,
    borderRadius: RADIUS.round,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '600',
  },
  shadow: {
    position: 'absolute',
    bottom: 26,
    width: 120,
    height: 22,
    borderRadius: RADIUS.round,
    backgroundColor: 'rgba(0,0,0,0.16)',
  },
});
