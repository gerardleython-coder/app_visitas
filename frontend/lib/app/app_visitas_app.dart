import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/network/api_client.dart';
import '../core/network/api_repository.dart';
import '../core/session/session_cubit.dart';
import '../core/session/session_store.dart';
import '../core/theme/app_theme.dart';
import '../features/auth/login_screen.dart';
import '../features/home/app_shell.dart';

String resolveApiBaseUrl() {
  const override = String.fromEnvironment('API_BASE_URL');
  if (override.isNotEmpty) {
    return override;
  }

  if (kIsWeb) {
    return 'http://127.0.0.1:8000/api/v1';
  }

  return defaultTargetPlatform == TargetPlatform.android
      ? 'http://10.0.2.2:8000/api/v1'
      : 'http://127.0.0.1:8000/api/v1';
}

class AppVisitasApp extends StatefulWidget {
  const AppVisitasApp({super.key});

  @override
  State<AppVisitasApp> createState() => _AppVisitasAppState();
}

class _AppVisitasAppState extends State<AppVisitasApp> {
  late final SecureSessionStore _sessionStore;
  late final ApiRepository _repository;
  late final SessionCubit _sessionCubit;

  @override
  void initState() {
    super.initState();
    _sessionStore = SecureSessionStore();
    final baseUrl = resolveApiBaseUrl();
    final apiClient = ApiClient(baseUrl: baseUrl, sessionStore: _sessionStore);
    _repository = ApiRepository(
      client: apiClient,
      sessionStore: _sessionStore,
    );
    _sessionCubit = SessionCubit(gateway: _repository, store: _sessionStore);
    apiClient.onSessionExpired = _sessionCubit.expire;
  }

  @override
  void dispose() {
    _sessionCubit.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocProvider.value(
        value: _sessionCubit,
        child: MaterialApp(
          title: 'AppVisitas',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          home: _SessionGate(repository: _repository),
        ),
      );
}

class _SessionGate extends StatelessWidget {
  const _SessionGate({required this.repository});

  final ApiRepository repository;

  @override
  Widget build(BuildContext context) => BlocBuilder<SessionCubit, SessionState>(
        builder: (context, state) => switch (state.status) {
          SessionStatus.checking => const _SessionLoading(),
          SessionStatus.signedOut => LoginScreen(error: state.error),
          SessionStatus.signedIn => AppShell(
              account: state.account!,
              repository: repository,
            ),
        },
      );
}

class _SessionLoading extends StatelessWidget {
  const _SessionLoading();

  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 34,
                height: 34,
                child: CircularProgressIndicator(strokeWidth: 2.5),
              ),
              SizedBox(height: 18),
              Text('Verificando sesión'),
            ],
          ),
        ),
      );
}
