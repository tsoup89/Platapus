import { useState, useEffect } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  type User,
} from 'firebase/auth';
import { doc, setDoc, getDoc } from 'firebase/firestore';
import { auth, db } from '../services/firebase';
import type { UserProfile, NotificationPreferences } from '../types';

const DEFAULT_NOTIFICATION_PREFS: NotificationPreferences = {
  enabled: true,
  dailyReminderHour:   8,
  dailyReminderMinute: 0,
  advanceNotificationHours: 0,
};

export function useAuth() {
  const [user, setUser]       = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        const snap = await getDoc(doc(db, 'users', firebaseUser.uid));
        if (snap.exists()) {
          setProfile(snap.data() as UserProfile);
        }
      } else {
        setProfile(null);
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  async function signIn(email: string, password: string) {
    setError(null);
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } catch (e: any) {
      setError(e.message ?? 'Sign in failed');
      throw e;
    }
  }

  async function register(email: string, password: string, displayName: string) {
    setError(null);
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password);
      const newProfile: UserProfile = {
        uid:         cred.user.uid,
        email,
        displayName,
        notificationPreferences: DEFAULT_NOTIFICATION_PREFS,
      };
      await setDoc(doc(db, 'users', cred.user.uid), newProfile);
      setProfile(newProfile);
    } catch (e: any) {
      setError(e.message ?? 'Registration failed');
      throw e;
    }
  }

  async function signOut() {
    await firebaseSignOut(auth);
    setProfile(null);
  }

  async function updateNotificationPrefs(prefs: NotificationPreferences) {
    if (!user) return;
    await setDoc(
      doc(db, 'users', user.uid),
      { notificationPreferences: prefs },
      { merge: true },
    );
    setProfile((p) => p ? { ...p, notificationPreferences: prefs } : p);
  }

  return {
    user,
    profile,
    loading,
    error,
    signIn,
    register,
    signOut,
    updateNotificationPrefs,
  };
}
