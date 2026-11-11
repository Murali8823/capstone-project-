import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import QRCode from 'react-native-qrcode-svg';
import { SafeAreaView } from 'react-native-safe-area-context';

const API = process.env.EXPO_PUBLIC_API_URL || 'http://192.168.1.19:8765';
const REFRESH_MS = 1800;

type Role = 'sender' | 'scammer' | 'business';
type User = {
  id: string;
  name: string;
  upi: string;
  role: Role;
  balance: number;
  color: string;
  scam_score: number;
};
type Transaction = {
  id: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  scam_score: number;
  status: string;
  reason: string;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  blockchain_tx_hash: string | null;
};
type AppState = { users: User[]; transactions: Transaction[]; escrow: number; overview: Record<string, unknown> };

const money = (amount: number) => `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const statusColor: Record<string, string> = {
  APPROVED: '#16a57b', RELEASED: '#16a57b', ESCROW: '#e6a322', MANUAL_REVIEW: '#dc7b24',
  REJECTED: '#dc5260', REFUNDED: '#5386e8',
};

export default function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [receiverId, setReceiverId] = useState('business');
  const [amount, setAmount] = useState('250');
  const [online, setOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [qrUser, setQrUser] = useState('');
  const [scannerOpen, setScannerOpen] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch(`${API}/api/state`);
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      const data = (await response.json()) as AppState;
      setUsers(data.users);
      setTransactions(data.transactions);
      setOnline(true);
      setSelectedId((current) => current || data.users.find((u) => u.role === 'sender')?.id || '');
    } catch {
      setOnline(false);
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const me = users.find((u) => u.id === selectedId);
  const receiver = users.find((u) => u.id === receiverId);
  const senders = users.filter((u) => u.role === 'sender');
  const receivers = users.filter((u) => u.role === 'business' || u.role === 'scammer');
  const mine = useMemo(
    () => transactions.filter((tx) => tx.sender_id === selectedId || tx.receiver_id === selectedId),
    [transactions, selectedId],
  );

  async function request(path: string, body?: unknown) {
    const response = await fetch(`${API}${path}`, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function pay() {
    if (!me || me.role !== 'sender' || !receiver) return Alert.alert('Select a sender and receiver first.');
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) return Alert.alert('Enter an amount greater than zero.');
    setBusy(true);
    try {
      const result = await request('/api/payments', {
        sender_id: me.id,
        receiver_id: receiver.id,
        amount: value,
        scenario: 'mobile-demo',
      });
      Alert.alert(result.status, `${result.reason}\n\nTransaction ${result.id.slice(0, 8)}`);
      await refresh();
    } catch (error) {
      Alert.alert('Payment could not be submitted', error instanceof Error ? error.message : 'Check the backend connection.');
    } finally {
      setBusy(false);
    }
  }

  async function openScanner() {
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) return Alert.alert('Camera access is needed to scan a demo recipient QR.');
    }
    setScannerOpen(true);
  }

  function handleQr(value: string) {
    try {
      const decoded = JSON.parse(value);
      if (decoded.type !== 'shieldpay-user' || !receivers.some((user) => user.id === decoded.userId)) {
        return Alert.alert('Unknown recipient', 'Scan a ShieldPay business or scammer demo QR.');
      }
      setReceiverId(decoded.userId);
      setScannerOpen(false);
    } catch {
      Alert.alert('Invalid QR', 'This is not a ShieldPay demo QR code.');
    }
  }

  const incoming = transactions.filter((tx) => tx.receiver_id === selectedId);
  const pending = incoming.filter((tx) => tx.status === 'ESCROW' || tx.status === 'MANUAL_REVIEW');

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>shield<Text style={styles.brandAccent}>pay</Text></Text>
          <Text style={styles.kicker}>RISK AWARE PAYMENT DEMO</Text>
        </View>
        <View style={styles.connection}>
          <View style={[styles.dot, { backgroundColor: online ? '#23c68e' : '#f06b75' }]} />
          <Text style={styles.connectionText}>{online ? 'BACKEND CONNECTED' : 'RECONNECTING'}</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.card}>
          <Text style={styles.label}>THIS DEVICE · SELECT DEMO PROFILE</Text>
          <View style={styles.profileList}>
            {users.map((user) => (
              <Pressable key={user.id} onPress={() => setSelectedId(user.id)} style={[styles.profile, selectedId === user.id && styles.profileSelected]}>
                <View style={[styles.avatar, { backgroundColor: user.color }]}><Text style={styles.avatarText}>{user.name.slice(0, 1)}</Text></View>
                <View style={styles.profileText}>
                  <Text style={styles.profileName}>{user.name}</Text>
                  <Text style={styles.muted}>{roleName(user.role)}{user.role !== 'sender' ? ` · Score ${user.scam_score}%` : ''}</Text>
                </View>
                {selectedId === user.id && <Text style={styles.check}>✓</Text>}
              </Pressable>
            ))}
          </View>
        </View>

        {me && <>
          <View style={[styles.wallet, me.role === 'business' ? styles.walletBusiness : me.role === 'scammer' ? styles.walletScammer : undefined]}>
            <Text style={styles.walletLabel}>YOUR ROLE · {roleName(me.role).toUpperCase()}</Text>
            <Text style={styles.walletName}>{me.name}</Text>
            <Text style={styles.balance}>{money(me.balance)}</Text>
            <Text style={styles.walletLabel}>SIMULATED WALLET BALANCE</Text>
            {me.role !== 'sender' && <View style={styles.scoreRow}>
              <Text style={styles.walletLabel}>CURRENT RECEIVER SCAM SCORE</Text>
              <Text style={styles.score}>{me.scam_score}%</Text>
            </View>}
          </View>

          {me.role === 'sender' ? <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Send a demo payment</Text>
              <Text style={styles.muted}>The backend decides from the receiver’s current scam score.</Text>
              <Text style={styles.label}>RECEIVER</Text>
              {receivers.map((person) => <Pressable key={person.id} onPress={() => setReceiverId(person.id)} style={[styles.receiver, receiverId === person.id && styles.receiverSelected]}>
                <View style={[styles.avatarSmall, { backgroundColor: person.color }]}><Text style={styles.avatarText}>{person.name[0]}</Text></View>
                <View style={styles.profileText}><Text style={styles.profileName}>{person.name}</Text><Text style={styles.muted}>Scam score {person.scam_score}% · {person.upi}</Text></View>
                <Text style={[styles.decision, { color: decisionColor(person.scam_score) }]}>{decisionName(person.scam_score)}</Text>
              </Pressable>)}
              {receiver && <Text style={styles.riskNote}>At {receiver.scam_score}% the payment will {decisionVerb(receiver.scam_score)}.</Text>}
              <Text style={styles.label}>AMOUNT (₹)</Text>
              <TextInput value={amount} onChangeText={setAmount} keyboardType="decimal-pad" style={styles.amountInput} placeholder="250.00" placeholderTextColor="#708093" />
              <View style={styles.row}>
                <Pressable style={[styles.primaryButton, busy && styles.disabled]} onPress={pay} disabled={busy}>
                  <Text style={styles.primaryText}>{busy ? 'Submitting…' : 'Review and pay'}</Text>
                </Pressable>
                <Pressable style={styles.secondaryButton} onPress={() => setQrUser(me.id)}><Text style={styles.secondaryText}>My QR</Text></Pressable>
              </View>
              <Pressable style={styles.scanButton} onPress={openScanner}><Text style={styles.secondaryText}>Scan recipient QR</Text></Pressable>
            </View>
          </> : <>
            <View style={styles.metrics}>
              <Metric label="INCOMING" value={String(incoming.length)} />
              <Metric label="ESCROWED" value={String(pending.length)} />
              <Metric label="LOCKED" value={money(pending.reduce((sum, tx) => sum + tx.amount, 0))} />
            </View>
            {me.role === 'business' && <View style={styles.card}>
              <Text style={styles.cardTitle}>Business receiver view</Text>
              <Text style={styles.muted}>All three sender profiles use this shared receiver record. Set its score from the desktop admin dashboard.</Text>
            </View>}
            {me.role === 'scammer' && <View style={styles.card}>
              <Text style={styles.cardTitle}>Suspicious demo persona</Text>
              <Text style={styles.muted}>This is a demonstration receiver only. Payments are rejected while its score is above 80%.</Text>
            </View>}
            <Pressable style={styles.secondaryButton} onPress={() => setQrUser(me.id)}><Text style={styles.secondaryText}>Show receiver payment QR</Text></Pressable>
          </>}

          <View style={styles.historyHeader}>
            <Text style={styles.cardTitle}>{me.role === 'sender' ? 'Recent activity' : 'Incoming transactions'}</Text>
            <Pressable onPress={() => void refresh()}><Text style={styles.refresh}>Refresh</Text></Pressable>
          </View>
          {mine.slice(0, 20).map((tx) => <TransactionRow key={tx.id} tx={tx} me={me} users={users} />)}
          {!mine.length && <Text style={styles.empty}>Transactions shared with this profile will appear here.</Text>}
          <Text style={styles.footer}>Simulated balances only · updates every 1.8 seconds · no real payments</Text>
        </>}
      </ScrollView>

      <Modal visible={Boolean(qrUser)} transparent animationType="fade" onRequestClose={() => setQrUser('')}>
        <View style={styles.modalBackdrop}><View style={styles.qrCard}>
          <Text style={styles.cardTitle}>ShieldPay demo recipient QR</Text>
          {qrUser ? <QRCode value={JSON.stringify({ type: 'shieldpay-user', userId: qrUser })} size={220} /> : null}
          <Text style={styles.muted}>Scan from another ShieldPay device.</Text>
          <Pressable style={styles.primaryButton} onPress={() => setQrUser('')}><Text style={styles.primaryText}>Close</Text></Pressable>
        </View></View>
      </Modal>
      <Modal visible={scannerOpen} onRequestClose={() => setScannerOpen(false)}>
        <SafeAreaView style={styles.scanner}>
          <Pressable onPress={() => setScannerOpen(false)}><Text style={styles.secondaryText}>Close scanner</Text></Pressable>
          <Text style={styles.scanTitle}>Scan demo receiver QR</Text>
          <CameraView style={styles.camera} barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={({ data }) => handleQr(data)} />
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

function roleName(role: Role) {
  return role === 'sender' ? 'Legitimate sender' : role === 'business' ? 'Business receiver' : 'Scammer persona';
}
function decisionName(score: number) {
  return score < 50 ? 'APPROVED' : score <= 80 ? 'ESCROW' : 'REJECTED';
}
function decisionVerb(score: number) {
  return score < 50 ? 'transfer immediately' : score <= 80 ? 'lock funds in escrow' : 'be rejected with no debit';
}
function decisionColor(score: number) {
  return score < 50 ? '#16a57b' : score <= 80 ? '#d0921d' : '#dc5260';
}
function Metric({ label, value }: { label: string; value: string }) {
  return <View style={styles.metric}><Text style={styles.metricValue}>{value}</Text><Text style={styles.metricLabel}>{label}</Text></View>;
}
function TransactionRow({ tx, me, users }: { tx: Transaction; me: User; users: User[] }) {
  const outgoing = tx.sender_id === me.id;
  const other = users.find((user) => user.id === (outgoing ? tx.receiver_id : tx.sender_id));
  const time = new Date(tx.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return <View style={styles.txRow}>
    <View style={[styles.statusDot, { backgroundColor: statusColor[tx.status] || '#8491a0' }]} />
    <View style={styles.txMain}>
      <Text style={styles.profileName}>{outgoing ? 'To' : 'From'} {other?.name || 'Demo profile'}</Text>
      <Text style={styles.muted}>{tx.status} · Score {tx.scam_score}% · {time}</Text>
      <Text style={styles.reason} numberOfLines={2}>{tx.reason}</Text>
    </View>
    <Text style={styles.txAmount}>{money(tx.amount)}</Text>
  </View>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0a111b' },
  header: { minHeight: 72, paddingHorizontal: 18, backgroundColor: '#101b29', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderColor: '#213146' },
  brand: { color: '#f3f7fb', fontSize: 24, fontWeight: '800', letterSpacing: -0.7 }, brandAccent: { color: '#39c7e9' },
  kicker: { marginTop: 2, color: '#8999ad', fontSize: 9, letterSpacing: 1.5, fontWeight: '700' },
  connection: { flexDirection: 'row', alignItems: 'center', gap: 6 }, dot: { width: 8, height: 8, borderRadius: 4 }, connectionText: { color: '#c6d1dc', fontSize: 9, fontWeight: '700' },
  content: { padding: 16, paddingBottom: 36, gap: 14 },
  card: { backgroundColor: '#111e2d', borderRadius: 16, borderWidth: 1, borderColor: '#203149', padding: 16 },
  label: { marginTop: 13, marginBottom: 8, color: '#8292a7', fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  profileList: { gap: 6 }, profile: { minHeight: 54, paddingHorizontal: 9, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, borderWidth: 1, borderColor: 'transparent' }, profileSelected: { backgroundColor: '#182d40', borderColor: '#2d637b' },
  avatar: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center' }, avatarSmall: { width: 31, height: 31, borderRadius: 10, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: 'white', fontSize: 15, fontWeight: '800' }, profileText: { flex: 1 }, profileName: { color: '#eef3f8', fontSize: 13, fontWeight: '700' }, muted: { color: '#8b9aad', fontSize: 10, marginTop: 3 }, check: { color: '#39c7e9', fontWeight: '800' },
  wallet: { backgroundColor: '#126e79', borderRadius: 18, padding: 18 }, walletBusiness: { backgroundColor: '#145f70' }, walletScammer: { backgroundColor: '#713b4d' }, walletLabel: { color: '#c5e8ea', fontSize: 9, fontWeight: '700', letterSpacing: 1 }, walletName: { color: 'white', fontSize: 19, fontWeight: '700', marginTop: 10 }, balance: { color: 'white', fontSize: 32, fontWeight: '800', marginTop: 8 }, scoreRow: { borderTopWidth: 1, borderColor: '#ffffff35', marginTop: 15, paddingTop: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, score: { color: 'white', fontSize: 22, fontWeight: '800' },
  cardTitle: { color: '#f0f4f8', fontSize: 15, fontWeight: '700' }, receiver: { minHeight: 58, borderRadius: 12, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 9, borderWidth: 1, borderColor: '#25364b', marginBottom: 7 }, receiverSelected: { backgroundColor: '#172b3b', borderColor: '#399eb5' }, decision: { fontSize: 8, fontWeight: '900' }, riskNote: { color: '#9eb3c5', fontSize: 10, marginTop: 4 }, amountInput: { height: 50, borderRadius: 12, backgroundColor: '#0b1521', color: '#f7fafc', paddingHorizontal: 14, fontSize: 20, fontWeight: '700', borderWidth: 1, borderColor: '#25364b' },
  row: { flexDirection: 'row', gap: 8, marginTop: 12 }, primaryButton: { minHeight: 46, flex: 1, borderRadius: 12, backgroundColor: '#0987a4', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 14 }, primaryText: { color: 'white', fontWeight: '800', fontSize: 13 }, disabled: { opacity: 0.55 }, secondaryButton: { minHeight: 46, paddingHorizontal: 16, borderRadius: 12, backgroundColor: '#24364a', alignItems: 'center', justifyContent: 'center' }, secondaryText: { color: '#d9e5ee', fontWeight: '700', fontSize: 12 }, scanButton: { alignItems: 'center', padding: 12 },
  metrics: { flexDirection: 'row', gap: 8 }, metric: { flex: 1, minHeight: 72, borderRadius: 14, backgroundColor: '#111e2d', borderWidth: 1, borderColor: '#203149', alignItems: 'center', justifyContent: 'center', padding: 8 }, metricValue: { color: '#eaf1f7', fontWeight: '800', fontSize: 16 }, metricLabel: { color: '#8494a8', fontSize: 8, letterSpacing: 0.8, fontWeight: '800', marginTop: 5 },
  historyHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: 4 }, refresh: { color: '#4ec9e7', fontWeight: '700', fontSize: 11 }, txRow: { backgroundColor: '#111e2d', borderRadius: 13, borderWidth: 1, borderColor: '#203149', padding: 12, flexDirection: 'row', alignItems: 'flex-start', gap: 10 }, statusDot: { width: 9, height: 9, borderRadius: 5, marginTop: 5 }, txMain: { flex: 1 }, reason: { color: '#a2b0c0', fontSize: 10, marginTop: 4, lineHeight: 15 }, txAmount: { color: '#e8eff5', fontSize: 12, fontWeight: '800' }, empty: { color: '#8292a7', textAlign: 'center', padding: 22, fontSize: 11 }, footer: { color: '#74869b', fontSize: 9, textAlign: 'center', marginTop: 6 },
  modalBackdrop: { flex: 1, backgroundColor: '#000a', justifyContent: 'center', padding: 24 }, qrCard: { backgroundColor: '#f7fafc', borderRadius: 20, padding: 22, alignItems: 'center', gap: 16 }, scanner: { flex: 1, backgroundColor: '#0a111b', padding: 20, gap: 18 }, scanTitle: { color: 'white', textAlign: 'center', fontSize: 19, fontWeight: '700' }, camera: { flex: 1, borderRadius: 18, overflow: 'hidden' },
});
