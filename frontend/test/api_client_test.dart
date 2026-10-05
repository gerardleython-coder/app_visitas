import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_visitas/app/app_visitas_app.dart';
import 'package:app_visitas/core/network/api_client.dart';
import 'package:app_visitas/core/network/api_repository.dart';
import 'package:app_visitas/core/session/session_store.dart';

class _MemoryStore implements SessionStore {
  _MemoryStore({this.accessToken, this.refreshToken});

  String? accessToken;
  String? refreshToken;

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
    accessToken = null;
    refreshToken = null;
  }
}

class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this.respond);

  final ResponseBody Function(RequestOptions request) respond;
  final requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return respond(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _jsonResponse(int status, Object? value) =>
    ResponseBody.fromString(
      value == null ? '' : jsonEncode(value),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json']
      },
    );

ApiClient _apiClient(_MemoryStore store, _ScriptedAdapter adapter) {
  final client = ApiClient(
    baseUrl: 'https://api.example.test/api/v1',
    sessionStore: store,
  );
  client.dio.httpClientAdapter = adapter;
  return client;
}

void main() {
  test('resolves the backend URL for mobile and web targets', () {
    final resolved = resolveApiBaseUrl();
    expect(resolved, contains('api/v1'));
    expect(resolved.startsWith('http://'), isTrue);
  });

  test('rotates refresh credentials and retries a protected request', () async {
    final store = _MemoryStore(
      accessToken: 'expired-access',
      refreshToken: 'current-refresh',
    );
    final adapter = _ScriptedAdapter((request) {
      if (request.uri.path.endsWith('/auth/refresh')) {
        return _jsonResponse(200, {
          'access_token': 'rotated-access',
          'refresh_token': 'rotated-refresh',
          'expires_in': 900,
          'token_type': 'bearer',
        });
      }
      if (request.headers['Authorization'] == 'Bearer rotated-access') {
        return _jsonResponse(200, {'ok': true});
      }
      return _jsonResponse(401, {'detail': 'expired'});
    });
    final client = _apiClient(store, adapter);

    final response = await client.dio.get<Map<String, dynamic>>('protected');

    expect(response.data, {'ok': true});
    expect(store.accessToken, 'rotated-access');
    expect(store.refreshToken, 'rotated-refresh');
    expect(adapter.requests.map((request) => request.uri.path), [
      '/api/v1/protected',
      '/api/v1/auth/refresh',
      '/api/v1/protected',
    ]);
    expect(
      adapter.requests.last.headers['Authorization'],
      'Bearer rotated-access',
    );
    client.dio.close(force: true);
  });

  test('clears credentials and expires the session when refresh is rejected',
      () async {
    final store = _MemoryStore(
      accessToken: 'expired-access',
      refreshToken: 'revoked-refresh',
    );
    final adapter = _ScriptedAdapter((_) => _jsonResponse(401, {
          'detail': {'code': 'unauthorized', 'message': 'Unauthorized'},
        }));
    final client = _apiClient(store, adapter);
    var expired = false;
    client.onSessionExpired = () async => expired = true;

    await expectLater(
      client.dio.get<void>('protected'),
      throwsA(isA<DioException>()),
    );

    expect(store.accessToken, isNull);
    expect(store.refreshToken, isNull);
    expect(expired, isTrue);
    expect(adapter.requests.map((request) => request.uri.path), [
      '/api/v1/protected',
      '/api/v1/auth/refresh',
    ]);
    client.dio.close(force: true);
  });

  test('logout clears local credentials after the API call', () async {
    final store = _MemoryStore(
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    );
    final adapter = _ScriptedAdapter((request) {
      expect(request.uri.path, '/api/v1/auth/logout');
      expect(request.method, 'POST');
      expect(request.headers['Authorization'], 'Bearer access-token');
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    await repository.logout();

    expect(store.accessToken, isNull);
    expect(store.refreshToken, isNull);
    client.dio.close(force: true);
  });

  test('loads audit history for a visit', () async {
    final store = _MemoryStore(accessToken: 'access-token');
    final adapter = _ScriptedAdapter((request) {
      expect(request.uri.path, '/api/v1/visitas/visit-1/history');
      return _jsonResponse(200, [
        {
          'id': 'history-1',
          'visit_id': 'visit-1',
          'actor_id': 'actor-1',
          'action': 'REPROGRAMADA',
          'previous_status': 'PROGRAMADA',
          'new_status': 'PROGRAMADA',
          'previous_scheduled_at': '2026-09-28T17:30:00Z',
          'new_scheduled_at': '2026-09-29T17:30:00Z',
          'previous_values': null,
          'new_values': null,
          'reason': 'Cambio coordinado',
          'created_at': '2026-09-28T18:00:00Z',
        },
      ]);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    final history = await repository.visitHistory('visit-1');

    expect(history, hasLength(1));
    expect(history.single.action, 'REPROGRAMADA');
    expect(history.single.previousStatus, 'PROGRAMADA');
    expect(history.single.reason, 'Cambio coordinado');
    expect(
      history.single.newScheduledAt,
      DateTime.parse('2026-09-29T17:30:00Z'),
    );
    client.dio.close(force: true);
  });

  test('district CRUD uses the territorial API routes', () async {
    final store = _MemoryStore(accessToken: 'discardable-access');
    final adapter = _ScriptedAdapter((request) {
      if (request.method == 'POST') {
        expect(request.uri.path, '/api/v1/admin/distritos');
        expect(request.data, {'name': 'Distrito Norte'});
        return _jsonResponse(
            201, {'id': 'district-1', 'name': 'Distrito Norte'});
      }
      if (request.method == 'PATCH') {
        expect(request.uri.path, '/api/v1/admin/distritos/district-1');
        expect(request.data, {'name': 'Distrito Central'});
        return _jsonResponse(
            200, {'id': 'district-1', 'name': 'Distrito Central'});
      }
      expect(request.method, 'DELETE');
      expect(request.uri.path, '/api/v1/admin/distritos/district-1');
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    final district = await repository.createDistrict('Distrito Norte');
    final updated =
        await repository.updateDistrict(district.id, 'Distrito Central');
    await repository.deleteDistrict(updated.id);

    expect(updated.name, 'Distrito Central');
    expect(adapter.requests.map((request) => request.method),
        ['POST', 'PATCH', 'DELETE']);
    client.dio.close(force: true);
  });

  test('administrator CRUD uses its isolated API routes', () async {
    final store = _MemoryStore(accessToken: 'discardable-access');
    final adapter = _ScriptedAdapter((request) {
      if (request.method == 'GET') {
        expect(request.uri.path, '/api/v1/users/administradores');
        return _jsonResponse(200, [
          {
            'id': 'admin-1',
            'name': 'Ana',
            'surname': 'Admin',
            'email': 'ana@example.test',
            'role': 'ADMIN',
            'active': true,
            'district_id': null,
            'church_id': null,
          },
        ]);
      }
      if (request.method == 'POST') {
        if (request.uri.path.endsWith('/reactivar')) {
          expect(request.uri.path,
              '/api/v1/users/administradores/admin-2/reactivar');
          return _jsonResponse(200, {
            'id': 'admin-2',
            'name': 'Luis Alberto',
            'surname': 'Admin',
            'email': 'luis@example.test',
            'role': 'ADMIN',
            'active': true,
            'district_id': null,
            'church_id': null,
          });
        }
        expect(request.uri.path, '/api/v1/users/administradores');
        expect(request.data, {
          'name': 'Luis',
          'surname': 'Admin',
          'email': 'luis@example.test',
          'password': 'private-password',
        });
        return _jsonResponse(201, {
          'id': 'admin-2',
          'name': 'Luis',
          'surname': 'Admin',
          'email': 'luis@example.test',
          'role': 'ADMIN',
          'active': true,
          'district_id': null,
          'church_id': null,
        });
      }
      if (request.method == 'PATCH') {
        expect(request.uri.path, '/api/v1/users/administradores/admin-2');
        expect(request.data, {'name': 'Luis Alberto'});
        return _jsonResponse(200, {
          'id': 'admin-2',
          'name': 'Luis Alberto',
          'surname': 'Admin',
          'email': 'luis@example.test',
          'role': 'ADMIN',
          'active': true,
          'district_id': null,
          'church_id': null,
        });
      }
      expect(request.method, 'DELETE');
      expect(request.uri.path, '/api/v1/users/administradores/admin-2');
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    final listed = await repository.administrators();
    final created = await repository.createAdministrator(
      name: 'Luis',
      surname: 'Admin',
      email: 'luis@example.test',
      password: 'private-password',
    );
    final updated = await repository.updateAdministrator(created.id, {
      'name': 'Luis Alberto',
    });
    await repository.deactivateAdministrator(updated.id);
    final reactivated = await repository.reactivateAdministrator(updated.id);

    expect(listed.single.districtId, isNull);
    expect(listed.single.churchId, isNull);
    expect(updated.name, 'Luis Alberto');
    expect(reactivated.active, isTrue);
    expect(adapter.requests.map((request) => request.method), [
      'GET',
      'POST',
      'PATCH',
      'DELETE',
      'POST',
    ]);
    client.dio.close(force: true);
  });

  test('brother CRUD preserves required church and leader assignments',
      () async {
    final store = _MemoryStore(accessToken: 'discardable-access');
    final adapter = _ScriptedAdapter((request) {
      if (request.method == 'POST') {
        expect(request.uri.path, '/api/v1/hermanos');
        expect(request.data, {
          'name': 'Hermana',
          'surname': 'Ejemplo',
          'phone': '3000000000',
          'address': 'Bogotá',
          'district_id': 'district-1',
          'church_id': 'church-1',
          'leader_id': 'leader-1',
        });
        return _jsonResponse(201, {
          'id': 'brother-1',
          'name': 'Hermana',
          'surname': 'Ejemplo',
          'phone': '3000000000',
          'address': 'Bogotá',
          'district_id': 'district-1',
          'church_id': 'church-1',
          'leader_id': 'leader-1',
          'active': true,
        });
      }
      if (request.method == 'PATCH') {
        expect(request.uri.path, '/api/v1/hermanos/brother-1');
        expect(request.data, {'phone': '3000000001'});
        return _jsonResponse(200, {
          'id': 'brother-1',
          'name': 'Hermana',
          'surname': 'Ejemplo',
          'phone': '3000000001',
          'address': 'Bogotá',
          'district_id': 'district-1',
          'church_id': 'church-1',
          'leader_id': 'leader-1',
          'active': true,
        });
      }
      expect(request.method, 'DELETE');
      expect(request.uri.path, '/api/v1/hermanos/brother-1');
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    final brother = await repository.createBrother(
      name: 'Hermana',
      surname: 'Ejemplo',
      phone: '3000000000',
      address: 'Bogotá',
      districtId: 'district-1',
      churchId: 'church-1',
      leaderId: 'leader-1',
    );
    final updated =
        await repository.updateBrother(brother.id, {'phone': '3000000001'});
    await repository.deactivateBrother(updated.id);

    expect(updated.phone, '3000000001');
    expect(adapter.requests.map((request) => request.method),
        ['POST', 'PATCH', 'DELETE']);
    client.dio.close(force: true);
  });

  test('visit scheduling and cancellation send the required fields', () async {
    final store = _MemoryStore(accessToken: 'discardable-access');
    final adapter = _ScriptedAdapter((request) {
      if (request.method == 'POST') {
        expect(request.uri.path, '/api/v1/visitas');
        expect(request.data, {
          'brother_id': 'brother-1',
          'visit_type': 'CUIDADO_PASTORAL',
          'scheduled_at': '2026-09-29T17:30:00.000Z',
          'duration_minutes': 45,
          'location': 'Bogotá',
          'observations': 'Seguimiento',
        });
        return _jsonResponse(201, {
          'id': 'visit-1',
          'brother_id': 'brother-1',
          'leader_id': 'leader-1',
          'visit_type': 'CUIDADO_PASTORAL',
          'scheduled_at': '2026-09-29T17:30:00Z',
          'completed_at': null,
          'duration_minutes': 45,
          'location': 'Bogotá',
          'observations': 'Seguimiento',
          'status': 'PROGRAMADA',
          'cancellation_reason': null,
        });
      }
      expect(request.method, 'DELETE');
      expect(request.uri.path, '/api/v1/visitas/visit-1');
      expect(request.data, {'reason': 'Cambio de agenda'});
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    final visit = await repository.createVisit(
      brotherId: 'brother-1',
      visitType: 'CUIDADO_PASTORAL',
      scheduledAt: DateTime.utc(2026, 9, 29, 17, 30),
      durationMinutes: 45,
      location: 'Bogotá',
      observations: 'Seguimiento',
    );
    await repository.cancelVisit(visit.id, 'Cambio de agenda');

    expect(visit.status, 'PROGRAMADA');
    expect(
        adapter.requests.map((request) => request.method), ['POST', 'DELETE']);
    client.dio.close(force: true);
  });

  test('password reset and change use their API contracts and clear session',
      () async {
    final store = _MemoryStore(
      accessToken: 'discardable-access',
      refreshToken: 'discardable-refresh',
    );
    final adapter = _ScriptedAdapter((request) {
      if (request.uri.path.endsWith('/auth/password/reset')) {
        expect(request.data, {
          'token': 'discardable-reset-value',
          'new_password': 'discardable-new-password',
        });
        return _jsonResponse(204, null);
      }
      expect(request.uri.path, '/api/v1/auth/password/change');
      expect(request.data, {
        'current_password': 'discardable-current-password',
        'new_password': 'discardable-new-password',
      });
      return _jsonResponse(204, null);
    });
    final client = _apiClient(store, adapter);
    final repository = ApiRepository(client: client, sessionStore: store);

    await repository.resetPassword(
      ' discardable-reset-value ',
      'discardable-new-password',
    );
    expect(store.accessToken, isNull);
    expect(store.refreshToken, isNull);

    await store.writeTokens(
      accessToken: 'discardable-access',
      refreshToken: 'discardable-refresh',
    );
    await repository.changePassword(
      'discardable-current-password',
      'discardable-new-password',
    );

    expect(store.accessToken, isNull);
    expect(store.refreshToken, isNull);
    client.dio.close(force: true);
  });
}
