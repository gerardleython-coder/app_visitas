import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_visitas/core/models/api_models.dart';
import 'package:app_visitas/core/network/api_repository.dart';
import 'package:app_visitas/core/session/session_cubit.dart';
import 'package:app_visitas/core/session/session_store.dart';
import 'package:app_visitas/core/time/bogota_time.dart';

const _account = CurrentAccount(
  id: '00000000-0000-4000-8000-000000000001',
  email: 'pastor@example.test',
  role: AppRole.pastor,
  active: true,
  districtId: '00000000-0000-4000-8000-000000000002',
  churchId: '00000000-0000-4000-8000-000000000003',
);

class _MemorySessionStore implements SessionStore {
  _MemorySessionStore({this.accessToken, this.refreshToken});

  String? accessToken;
  String? refreshToken;
  bool cleared = false;

  @override
  Future<String?> readAccessToken() async => accessToken;

  @override
  Future<String?> readRefreshToken() async => refreshToken;

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  @override
  Future<void> clear() async {
    cleared = true;
    accessToken = null;
    refreshToken = null;
  }
}

class _SessionGatewayFake implements SessionGateway {
  CurrentAccount account = _account;
  bool rejectLogin = false;
  String? resetEmail;

  @override
  Future<CurrentAccount> currentAccount() async => account;

  @override
  Future<CurrentAccount> login(String email, String password) async {
    if (rejectLogin) throw Exception('denied');
    return account;
  }

  @override
  Future<void> restorePassword(String email) async {
    resetEmail = email;
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {}

  @override
  Future<void> changePassword(
      String currentPassword, String newPassword) async {}

  @override
  Future<void> logout() async {}
}

void main() {
  setUp(BogotaTime.initialize);

  blocTest<SessionCubit, SessionState>(
    'restores the server identity when secure tokens exist',
    build: () => SessionCubit(
      gateway: _SessionGatewayFake(),
      store:
          _MemorySessionStore(accessToken: 'access', refreshToken: 'refresh'),
    ),
    wait: const Duration(milliseconds: 10),
    expect: () => [
      isA<SessionState>().having(
        (state) => state.status,
        'status',
        SessionStatus.signedIn,
      ),
    ],
    verify: (cubit) {
      expect(cubit.state.account?.role, AppRole.pastor);
      expect(cubit.state.account?.churchId, _account.churchId);
    },
  );

  blocTest<SessionCubit, SessionState>(
    'does not keep an unverified login after authentication fails',
    build: () {
      final gateway = _SessionGatewayFake()..rejectLogin = true;
      return SessionCubit(gateway: gateway, store: _MemorySessionStore());
    },
    act: (cubit) async {
      await Future<void>.delayed(Duration.zero);
      await cubit.signIn('pastor@example.test', 'wrong');
    },
    expect: () => [
      isA<SessionState>()
          .having((state) => state.status, 'status', SessionStatus.signedOut),
      isA<SessionState>()
          .having((state) => state.status, 'status', SessionStatus.checking),
      isA<SessionState>()
          .having((state) => state.status, 'status', SessionStatus.signedOut)
          .having((state) => state.error, 'error',
              'No fue posible iniciar sesión.'),
    ],
  );

  test('interprets local wall-clock input and API instants in Bogota', () {
    final utc = BogotaTime.wallClockToUtc(
      year: 2026,
      month: 9,
      day: 28,
      hour: 12,
      minute: 30,
    );

    expect(utc.toIso8601String(), '2026-09-28T17:30:00.000Z');
    final displayed = BogotaTime.display(utc);
    expect(displayed.hour, 12);
    expect(displayed.minute, 30);
    expect(displayed.timeZoneOffset, const Duration(hours: -5));
  });

  test('expires the local session and clears both rotated credentials',
      () async {
    final store =
        _MemorySessionStore(accessToken: 'access', refreshToken: 'refresh');
    final cubit = SessionCubit(gateway: _SessionGatewayFake(), store: store);
    await Future<void>.delayed(const Duration(milliseconds: 10));

    await cubit.expire();

    expect(cubit.state.status, SessionStatus.signedOut);
    expect(store.accessToken, isNull);
    expect(store.refreshToken, isNull);
    await cubit.close();
  });
}
