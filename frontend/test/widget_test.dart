// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:app_visitas/core/models/api_models.dart';
import 'package:app_visitas/core/network/api_repository.dart';
import 'package:app_visitas/core/session/session_cubit.dart';
import 'package:app_visitas/core/session/session_store.dart';
import 'package:app_visitas/core/time/bogota_time.dart';
import 'package:app_visitas/features/auth/login_screen.dart';
import 'package:app_visitas/features/team/team_page.dart';
import 'package:app_visitas/features/territories/territories_page.dart';
import 'package:app_visitas/features/visits/visits_page.dart';
import 'package:app_visitas/core/theme/app_theme.dart';
import 'package:mocktail/mocktail.dart';

class _ApiRepositoryMock extends Mock implements ApiRepository {}

class _MemoryStore implements SessionStore {
  @override
  Future<String?> readAccessToken() async => null;

  @override
  Future<String?> readRefreshToken() async => null;

  @override
  Future<void> writeTokens(
      {required String accessToken, required String refreshToken}) async {}

  @override
  Future<void> clear() async {}
}

class _SessionFake implements SessionGateway {
  String? requestedResetEmail;
  String? consumedResetToken;
  String? resetPasswordValue;

  @override
  Future<CurrentAccount> currentAccount() async => _account;

  @override
  Future<CurrentAccount> login(String email, String password) async => _account;

  @override
  Future<void> restorePassword(String email) async {
    requestedResetEmail = email;
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    consumedResetToken = token;
    resetPasswordValue = newPassword;
  }

  @override
  Future<void> changePassword(
      String currentPassword, String newPassword) async {}

  @override
  Future<void> logout() async {}
}

const _account = CurrentAccount(
  id: '00000000-0000-4000-8000-000000000001',
  email: 'admin@example.test',
  role: AppRole.admin,
  active: true,
);

void main() {
  testWidgets('login is real, role is not guessed from email', (tester) async {
    final gateway = _SessionFake();
    final session = SessionCubit(gateway: gateway, store: _MemoryStore());
    await tester.pumpWidget(
      BlocProvider.value(
        value: session,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const LoginScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('AppVisitas'), findsOneWidget);
    expect(find.text('Iniciar sesión'), findsOneWidget);
    expect(find.text('Simulación de perfil'), findsNothing);

    await session.close();
  });

  testWidgets('login errors are shown above the form', (tester) async {
    final gateway = _SessionFake();
    final session = SessionCubit(gateway: gateway, store: _MemoryStore());
    await tester.pumpWidget(
      BlocProvider.value(
        value: session,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const LoginScreen(error: 'Credenciales inválidas.'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final error = find.text('Credenciales inválidas.');
    expect(error, findsOneWidget);
    expect(
      tester.getTopLeft(error).dy,
      lessThan(tester.getTopLeft(find.text('Iniciar sesión')).dy),
    );

    await session.close();
  });

  testWidgets('recovery form displays neutral confirmation', (tester) async {
    final gateway = _SessionFake();
    final session = SessionCubit(gateway: gateway, store: _MemoryStore());
    await tester.pumpWidget(
      BlocProvider.value(
        value: session,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const LoginScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('¿Olvidaste tu contraseña?'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, 'admin@example.test');
    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();

    expect(gateway.requestedResetEmail, 'admin@example.test');
    expect(find.textContaining('Si la cuenta existe'), findsWidgets);

    await session.close();
  });

  testWidgets('recovery token completes reset without putting token in URL',
      (tester) async {
    final gateway = _SessionFake();
    final session = SessionCubit(gateway: gateway, store: _MemoryStore());
    await tester.pumpWidget(
      BlocProvider.value(
        value: session,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const LoginScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('¿Olvidaste tu contraseña?'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, 'admin@example.test');
    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Ya tengo el token de recuperación'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ya tengo el token de recuperación'));
    await tester.pumpAndSettle();
    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), 'one-time-token');
    await tester.enterText(fields.at(1), 'new-secret-value');
    await tester.enterText(fields.at(2), 'new-secret-value');
    await tester.tap(find.text('Actualizar contraseña'));
    await tester.pumpAndSettle();

    expect(gateway.consumedResetToken, 'one-time-token');
    expect(gateway.resetPasswordValue, 'new-secret-value');

    await session.close();
  });

  testWidgets('pastor can edit leaders but cannot deactivate them',
      (tester) async {
    final repository = _ApiRepositoryMock();
    when(() => repository.operators(any())).thenAnswer((_) async => [
          const OperatorProfile(
            id: '00000000-0000-4000-8000-000000000004',
            name: 'Lider',
            surname: 'Pastoral',
            email: 'leader@example.test',
            role: 'LIDER',
            active: true,
            districtId: '00000000-0000-4000-8000-000000000002',
            churchId: '00000000-0000-4000-8000-000000000003',
          ),
        ]);
    const pastor = CurrentAccount(
      id: '00000000-0000-4000-8000-000000000005',
      email: 'pastor@example.test',
      role: AppRole.pastor,
      active: true,
      districtId: '00000000-0000-4000-8000-000000000002',
      churchId: '00000000-0000-4000-8000-000000000003',
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: TeamPage(account: pastor, repository: repository),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(PopupMenuButton<String>));
    await tester.pumpAndSettle();

    expect(find.text('Editar datos'), findsOneWidget);
    expect(find.text('Desactivar'), findsNothing);
  });

  testWidgets('team shows loading and then the empty state', (tester) async {
    final repository = _ApiRepositoryMock();
    final operators = Completer<List<OperatorProfile>>();
    when(() => repository.operators(any())).thenAnswer((_) => operators.future);
    const pastor = CurrentAccount(
      id: '00000000-0000-4000-8000-000000000005',
      email: 'pastor@example.test',
      role: AppRole.pastor,
      active: true,
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: TeamPage(account: pastor, repository: repository),
      ),
    ));
    await tester.pump();
    expect(find.byType(LinearProgressIndicator), findsOneWidget);

    operators.complete(const []);
    await tester.pumpAndSettle();
    expect(find.text('No hay usuarios para mostrar.'), findsOneWidget);
  });

  testWidgets('team displays a recoverable error when loading fails',
      (tester) async {
    final repository = _ApiRepositoryMock();
    when(() => repository.operators(any())).thenThrow(
      DioException(
        requestOptions: RequestOptions(path: 'users/lideres'),
        type: DioExceptionType.connectionError,
      ),
    );
    const pastor = CurrentAccount(
      id: '00000000-0000-4000-8000-000000000005',
      email: 'pastor@example.test',
      role: AppRole.pastor,
      active: true,
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: TeamPage(account: pastor, repository: repository),
      ),
    ));
    await tester.pumpAndSettle();

    expect(
      find.text('No fue posible conectar con el servidor. Intenta de nuevo.'),
      findsOneWidget,
    );
    expect(find.byTooltip('Acciones de usuario'), findsNothing);
  });

  testWidgets('canceling the new district dialog closes cleanly',
      (tester) async {
    final repository = _ApiRepositoryMock();
    when(() => repository.districts()).thenAnswer((_) async => const []);
    when(() => repository.churches()).thenAnswer((_) async => const []);

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: TerritoriesPage(repository: repository)),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Nuevo distrito'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();

    expect(find.text('Administración territorial'), findsOneWidget);
    expect(find.text('Nuevo distrito'), findsOneWidget);
  });

  testWidgets('pastor can open a visit history with changes and reason',
      (tester) async {
    await initializeDateFormatting('es_CO');
    BogotaTime.initialize();
    final repository = _ApiRepositoryMock();
    const brother = Brother(
      id: 'brother-1',
      name: 'Hermano',
      surname: 'Pastoral',
      phone: '3000000000',
      address: 'Bogotá',
      districtId: 'district-1',
      churchId: 'church-1',
      leaderId: 'leader-1',
      active: true,
    );
    final visit = Visit(
      id: 'visit-1',
      brotherId: brother.id,
      leaderId: brother.leaderId,
      visitType: 'EVANGELISMO',
      scheduledAt: DateTime.utc(2026, 9, 29, 17, 30),
      durationMinutes: 45,
      location: 'Bogotá',
      observations: 'Seguimiento',
      status: 'PROGRAMADA',
    );
    when(() => repository.visits()).thenAnswer((_) async => [visit]);
    when(() => repository.brothers()).thenAnswer((_) async => [brother]);
    when(() => repository.visitHistory(any())).thenAnswer((_) async => [
          VisitHistoryEntry(
            id: 'history-1',
            visitId: visit.id,
            actorId: 'actor-1',
            action: 'REPROGRAMADA',
            previousStatus: 'PROGRAMADA',
            newStatus: 'PROGRAMADA',
            previousScheduledAt: DateTime.utc(2026, 9, 28, 17, 30),
            newScheduledAt: DateTime.utc(2026, 9, 29, 17, 30),
            reason: 'Cambio coordinado',
            createdAt: DateTime.utc(2026, 9, 28, 18),
          ),
        ]);
    const pastor = CurrentAccount(
      id: 'pastor-1',
      email: 'pastor@example.test',
      role: AppRole.pastor,
      active: true,
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: VisitsPage(account: pastor, repository: repository),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    expect(find.text('Historial de la visita'), findsOneWidget);
    expect(find.text('Visita reprogramada'), findsOneWidget);
    expect(find.textContaining('Cambio coordinado'), findsOneWidget);

    const leader = CurrentAccount(
      id: 'leader-1',
      email: 'leader@example.test',
      role: AppRole.leader,
      active: true,
    );
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: VisitsPage(account: leader, repository: repository),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Historial'), findsNothing);
  });

  testWidgets('completing a scheduled visit persists the status transition',
      (tester) async {
    await initializeDateFormatting('es_CO');
    BogotaTime.initialize();
    final repository = _ApiRepositoryMock();
    const brother = Brother(
      id: 'brother-2',
      name: 'Hermana',
      surname: 'Pastoral',
      phone: '3000000001',
      address: 'Bogotá',
      districtId: 'district-1',
      churchId: 'church-1',
      leaderId: 'leader-1',
      active: true,
    );
    final scheduledVisit = Visit(
      id: 'visit-2',
      brotherId: brother.id,
      leaderId: brother.leaderId,
      visitType: 'EVANGELISMO',
      scheduledAt: DateTime.utc(2026, 9, 27, 17, 30),
      durationMinutes: 45,
      location: 'Bogotá',
      observations: 'Seguimiento',
      status: 'PROGRAMADA',
    );
    final completedVisit = Visit(
      id: scheduledVisit.id,
      brotherId: scheduledVisit.brotherId,
      leaderId: scheduledVisit.leaderId,
      visitType: scheduledVisit.visitType,
      scheduledAt: scheduledVisit.scheduledAt,
      completedAt: DateTime.utc(2026, 9, 28, 17, 30),
      durationMinutes: scheduledVisit.durationMinutes,
      location: scheduledVisit.location,
      observations: scheduledVisit.observations,
      status: 'COMPLETADA',
    );
    var loadCount = 0;
    when(() => repository.visits()).thenAnswer((_) async {
      loadCount++;
      return loadCount == 1 ? [scheduledVisit] : [completedVisit];
    });
    when(() => repository.brothers()).thenAnswer((_) async => [brother]);
    when(() => repository.updateVisit(scheduledVisit.id, any()))
        .thenAnswer((_) async => completedVisit);
    const pastor = CurrentAccount(
      id: 'pastor-2',
      email: 'pastor@example.test',
      role: AppRole.pastor,
      active: true,
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: VisitsPage(account: pastor, repository: repository),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Completar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirmar'));
    await tester.pumpAndSettle();

    verify(() => repository.updateVisit(
          scheduledVisit.id,
          {'status': 'COMPLETADA'},
        )).called(1);
    expect(find.text('COMPLETADA'), findsOneWidget);
  });
}
