import 'package:dio/dio.dart';

import '../models/api_models.dart';
import '../session/session_store.dart';
import 'api_client.dart';

abstract interface class SessionGateway {
  Future<CurrentAccount> login(String email, String password);

  Future<CurrentAccount> currentAccount();

  Future<void> restorePassword(String email);

  Future<void> resetPassword(String token, String newPassword);

  Future<void> changePassword(String currentPassword, String newPassword);

  Future<void> logout();
}

class ApiRepository implements SessionGateway {
  ApiRepository({required ApiClient client, required SessionStore sessionStore})
      : _client = client,
        _sessionStore = sessionStore;

  final ApiClient _client;
  final SessionStore _sessionStore;
  Dio get _dio => _client.dio;

  @override
  Future<CurrentAccount> login(String email, String password) async {
    final response = await _dio.post<Map<String, dynamic>>(
      'auth/login',
      data: {'email': email, 'password': password},
    );
    final body = response.data!;
    await _sessionStore.writeTokens(
      accessToken: body['access_token'] as String,
      refreshToken: body['refresh_token'] as String,
    );
    return currentAccount();
  }

  @override
  Future<CurrentAccount> currentAccount() async {
    final response = await _dio.get<Map<String, dynamic>>('auth/me');
    return CurrentAccount.fromJson(response.data!);
  }

  @override
  Future<void> restorePassword(String email) async {
    await _dio.post<void>('auth/password/forgot', data: {'email': email});
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    await _dio.post<void>(
      'auth/password/reset',
      data: {'token': token.trim(), 'new_password': newPassword},
    );
    await _sessionStore.clear();
  }

  @override
  Future<void> changePassword(
      String currentPassword, String newPassword) async {
    await _dio.post<void>(
      'auth/password/change',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
    await _sessionStore.clear();
  }

  @override
  Future<void> logout() async {
    final refreshToken = await _sessionStore.readRefreshToken();
    try {
      if (refreshToken != null) {
        await _dio
            .post<void>('auth/logout', data: {'refresh_token': refreshToken});
      }
    } on DioException {
      // Clearing local credentials is still required when the API is unreachable.
    } finally {
      await _sessionStore.clear();
    }
  }

  Future<List<District>> districts() =>
      _list('admin/distritos', District.fromJson);

  Future<District> createDistrict(String name) async => District.fromJson(
        (await _dio.post<Map<String, dynamic>>('admin/distritos',
                data: {'name': name}))
            .data!,
      );

  Future<District> updateDistrict(String id, String name) async =>
      District.fromJson(
        (await _dio.patch<Map<String, dynamic>>('admin/distritos/$id',
                data: {'name': name}))
            .data!,
      );

  Future<void> deleteDistrict(String id) =>
      _dio.delete<void>('admin/distritos/$id');

  Future<List<Church>> churches({String? districtId}) => _list(
        'admin/iglesias',
        Church.fromJson,
        queryParameters:
            districtId == null ? null : {'district_id': districtId},
      );

  Future<Church> createChurch({
    required String districtId,
    required String name,
    String? address,
  }) async =>
      Church.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          'admin/iglesias',
          data: {'district_id': districtId, 'name': name, 'address': address},
        ))
            .data!,
      );

  Future<Church> updateChurch(String id,
          {String? name, String? address}) async =>
      Church.fromJson(
        (await _dio.patch<Map<String, dynamic>>(
          'admin/iglesias/$id',
          data: {
            if (name != null) 'name': name,
            if (address != null) 'address': address,
          },
        ))
            .data!,
      );

  Future<void> deactivateChurch(String id) =>
      _dio.delete<void>('admin/iglesias/$id');

  Future<List<OperatorProfile>> operators(String role) => _list(
      'users/${role == 'PASTOR' ? 'pastores' : 'lideres'}',
      OperatorProfile.fromJson);

  Future<OperatorProfile> createOperator({
    required String role,
    required String name,
    required String surname,
    required String email,
    required String password,
    required String districtId,
    required String churchId,
  }) async =>
      OperatorProfile.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          'users/${role == 'PASTOR' ? 'pastores' : 'lideres'}',
          data: {
            'name': name,
            'surname': surname,
            'email': email,
            'password': password,
            'district_id': districtId,
            'church_id': churchId,
          },
        ))
            .data!,
      );

  Future<OperatorProfile> updateOperator(
    String id,
    String role,
    Map<String, dynamic> changes,
  ) async =>
      OperatorProfile.fromJson(
        (await _dio.patch<Map<String, dynamic>>(
          'users/${role == 'PASTOR' ? 'pastores' : 'lideres'}/$id',
          data: changes,
        ))
            .data!,
      );

  Future<void> deactivateOperator(String id, String role) => _dio
      .delete<void>('users/${role == 'PASTOR' ? 'pastores' : 'lideres'}/$id');

  Future<OperatorProfile> setPrimaryPastor(
          String churchId, String pastorId) async =>
      OperatorProfile.fromJson(
        (await _dio.patch<Map<String, dynamic>>(
          'admin/iglesias/$churchId/pastor-principal',
          data: {'pastor_id': pastorId},
        ))
            .data!,
      );

  Future<List<Brother>> brothers() => _list('hermanos', Brother.fromJson);

  Future<Brother> createBrother({
    required String name,
    required String surname,
    required String phone,
    required String address,
    required String districtId,
    required String churchId,
    String? leaderId,
  }) async =>
      Brother.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          'hermanos',
          data: {
            'name': name,
            'surname': surname,
            'phone': phone,
            'address': address,
            'district_id': districtId,
            'church_id': churchId,
            if (leaderId != null) 'leader_id': leaderId,
          },
        ))
            .data!,
      );

  Future<Brother> updateBrother(
          String id, Map<String, dynamic> changes) async =>
      Brother.fromJson(
        (await _dio.patch<Map<String, dynamic>>('hermanos/$id', data: changes))
            .data!,
      );

  Future<void> deactivateBrother(String id) =>
      _dio.delete<void>('hermanos/$id');

  Future<Brother> reassignBrother(String id, String leaderId) async =>
      Brother.fromJson(
        (await _dio.patch<Map<String, dynamic>>(
          'hermanos/$id/lider',
          data: {'leader_id': leaderId},
        ))
            .data!,
      );

  Future<List<Visit>> visits() => _list('visitas', Visit.fromJson);

  Future<Visit> createVisit({
    required String brotherId,
    required String visitType,
    required DateTime scheduledAt,
    required int durationMinutes,
    required String location,
    required String observations,
  }) async =>
      Visit.fromJson(
        (await _dio.post<Map<String, dynamic>>(
          'visitas',
          data: {
            'brother_id': brotherId,
            'visit_type': visitType,
            'scheduled_at': scheduledAt.toUtc().toIso8601String(),
            'duration_minutes': durationMinutes,
            'location': location,
            'observations': observations,
          },
        ))
            .data!,
      );

  Future<Visit> updateVisit(String id, Map<String, dynamic> changes) async =>
      Visit.fromJson(
          (await _dio.patch<Map<String, dynamic>>('visitas/$id', data: changes))
              .data!);

  Future<void> cancelVisit(String id, String reason) =>
      _dio.delete<void>('visitas/$id', data: {'reason': reason});

  Future<List<VisitHistoryEntry>> visitHistory(String id) =>
      _list('visitas/$id/history', VisitHistoryEntry.fromJson);

  Future<List<AuditEvent>> audit({int offset = 0, int limit = 100}) =>
      _list('audit', AuditEvent.fromJson,
          queryParameters: {'offset': offset, 'limit': limit});

  Future<List<RankingEntry>> ranking({
    required String period,
    required String churchId,
    DateTime? referenceDate,
  }) =>
      _list(
        'reports/ranking',
        RankingEntry.fromJson,
        queryParameters: {
          'period': period,
          'church_id': churchId,
          if (referenceDate != null)
            'reference_date':
                '${referenceDate.year.toString().padLeft(4, '0')}-${referenceDate.month.toString().padLeft(2, '0')}-${referenceDate.day.toString().padLeft(2, '0')}',
        },
      );

  Future<List<T>> _list<T>(
    String path,
    T Function(Map<String, dynamic>) parse, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final response = await _dio.get<List<dynamic>>(
      path,
      queryParameters: queryParameters,
    );
    return (response.data ?? const [])
        .map((item) => parse(Map<String, dynamic>.from(item as Map)))
        .toList(growable: false);
  }
}

String apiErrorMessage(Object error) {
  if (error is DioException) {
    final response = error.response?.data;
    if (response is Map<String, dynamic>) {
      final detail = response['detail'];
      if (detail is Map<String, dynamic> && detail['message'] is String) {
        return detail['message'] as String;
      }
      if (detail is String) return detail;
    }
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return 'No fue posible conectar con el servidor. Intenta de nuevo.';
    }
  }
  return 'Ocurrió un error inesperado. Intenta de nuevo.';
}
