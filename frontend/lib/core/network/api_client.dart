import 'package:dio/dio.dart';

import '../session/session_store.dart';

class ApiClient {
  ApiClient({required String baseUrl, required SessionStore sessionStore})
      : _sessionStore = sessionStore {
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl.endsWith('/') ? baseUrl : '$baseUrl/',
        connectTimeout: const Duration(seconds: 12),
        receiveTimeout: const Duration(seconds: 20),
        headers: const {'Content-Type': 'application/json'},
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final accessToken = await _sessionStore.readAccessToken();
          if (accessToken != null && accessToken.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $accessToken';
          }
          handler.next(options);
        },
        onError: _handleUnauthorized,
      ),
    );
  }

  final SessionStore _sessionStore;
  late final Dio dio;
  Future<void> Function()? onSessionExpired;
  Future<void>? _refreshInFlight;

  Future<void> _handleUnauthorized(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final request = error.requestOptions;
    final isAuthRequest = request.path.endsWith('auth/login') ||
        request.path.endsWith('auth/refresh');
    if (error.response?.statusCode != 401 ||
        isAuthRequest ||
        request.extra['retriedAfterRefresh'] == true) {
      handler.next(error);
      return;
    }

    try {
      _refreshInFlight ??= _refreshTokens();
      await _refreshInFlight;
      final accessToken = await _sessionStore.readAccessToken();
      if (accessToken == null) {
        throw const SessionExpiredException();
      }
      request
        ..headers['Authorization'] = 'Bearer $accessToken'
        ..extra['retriedAfterRefresh'] = true;
      handler.resolve(await dio.fetch<dynamic>(request));
    } on Object {
      await _sessionStore.clear();
      await onSessionExpired?.call();
      handler.next(error);
    } finally {
      _refreshInFlight = null;
    }
  }

  Future<void> _refreshTokens() async {
    final refreshToken = await _sessionStore.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) {
      throw const SessionExpiredException();
    }
    final response = await dio.post<Map<String, dynamic>>(
      'auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    final body = response.data;
    if (body == null) {
      throw const SessionExpiredException();
    }
    await _sessionStore.writeTokens(
      accessToken: body['access_token'] as String,
      refreshToken: body['refresh_token'] as String,
    );
  }
}

class SessionExpiredException implements Exception {
  const SessionExpiredException();
}
