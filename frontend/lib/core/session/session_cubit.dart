import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../models/api_models.dart';
import '../network/api_repository.dart';
import 'session_store.dart';

enum SessionStatus { checking, signedOut, signedIn }

class SessionState {
  const SessionState({
    required this.status,
    this.account,
    this.error,
  });

  const SessionState.checking() : this(status: SessionStatus.checking);
  const SessionState.signedOut({String? error})
      : this(status: SessionStatus.signedOut, error: error);
  const SessionState.signedIn(CurrentAccount account)
      : this(status: SessionStatus.signedIn, account: account);

  final SessionStatus status;
  final CurrentAccount? account;
  final String? error;
}

class SessionCubit extends Cubit<SessionState> {
  SessionCubit({required SessionGateway gateway, required SessionStore store})
      : _gateway = gateway,
        _store = store,
        super(const SessionState.checking()) {
    restore();
  }

  final SessionGateway _gateway;
  final SessionStore _store;

  Future<void> restore() async {
    try {
      final accessToken = await _store.readAccessToken();
      final refreshToken = await _store.readRefreshToken();
      if (accessToken == null || refreshToken == null) {
        emit(const SessionState.signedOut());
        return;
      }
      emit(SessionState.signedIn(await _gateway.currentAccount()));
    } on Object {
      await _store.clear();
      emit(const SessionState.signedOut());
    }
  }

  Future<void> signIn(String email, String password) async {
    emit(const SessionState.checking());
    try {
      emit(SessionState.signedIn(await _gateway.login(email.trim(), password)));
    } on DioException catch (error) {
      emit(SessionState.signedOut(error: _messageFrom(error)));
    } on Object {
      emit(const SessionState.signedOut(
          error: 'No fue posible iniciar sesión.'));
    }
  }

  Future<void> requestPasswordReset(String email) async {
    await _gateway.restorePassword(email.trim());
  }

  Future<void> resetPassword(String token, String newPassword) async {
    await _gateway.resetPassword(token, newPassword);
    emit(const SessionState.signedOut());
  }

  Future<void> changePassword(
      String currentPassword, String newPassword) async {
    await _gateway.changePassword(currentPassword, newPassword);
    emit(const SessionState.signedOut());
  }

  Future<void> signOut() async {
    await _gateway.logout();
    emit(const SessionState.signedOut());
  }

  Future<void> expire() async {
    await _store.clear();
    if (!isClosed) emit(const SessionState.signedOut());
  }

  String _messageFrom(DioException error) {
    final body = error.response?.data;
    if (body is Map<String, dynamic>) {
      final detail = body['detail'];
      if (detail is Map<String, dynamic> && detail['message'] is String) {
        return detail['message'] as String;
      }
    }
    if (error.response?.statusCode == 401) return 'Credenciales inválidas.';
    return 'No fue posible conectar con el servidor.';
  }
}
