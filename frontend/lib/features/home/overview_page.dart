import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/theme/app_theme.dart';

class OverviewPage extends StatefulWidget {
  const OverviewPage(
      {required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<OverviewPage> createState() => _OverviewPageState();
}

class _OverviewPageState extends State<OverviewPage> {
  late Future<_OverviewData> _overview;

  @override
  void initState() {
    super.initState();
    _overview = _load();
  }

  Future<_OverviewData> _load() async {
    final brothersFuture = widget.repository.brothers();
    final visitsFuture = widget.repository.visits();
    if (widget.account.role == AppRole.admin) {
      final data = await Future.wait<Object>([
        widget.repository.districts(),
        widget.repository.churches(),
        widget.repository.operators('PASTOR'),
        widget.repository.operators('LIDER'),
        brothersFuture,
        visitsFuture,
      ]);
      return _OverviewData(
        districts: data[0] as List<District>,
        churches: data[1] as List<Church>,
        operators: [
          ...data[2] as List<OperatorProfile>,
          ...data[3] as List<OperatorProfile>
        ],
        brothers: data[4] as List<Brother>,
        visits: data[5] as List<Visit>,
      );
    }
    final data = await Future.wait<Object>([
      if (widget.account.role == AppRole.pastor)
        widget.repository.operators('LIDER'),
      brothersFuture,
      visitsFuture,
    ]);
    final offset = widget.account.role == AppRole.pastor ? 1 : 0;
    return _OverviewData(
      operators: widget.account.role == AppRole.pastor
          ? data[0] as List<OperatorProfile>
          : const [],
      brothers: data[offset] as List<Brother>,
      visits: data[offset + 1] as List<Visit>,
    );
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() => _overview = next);
    await next;
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<_OverviewData>(
        future: _overview,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return _ProblemState(
              message: apiErrorMessage(snapshot.error!),
              onRetry: () => setState(() => _overview = _load()),
            );
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snapshot.data!;
          final scheduled =
              data.visits.where((visit) => visit.status == 'PROGRAMADA').length;
          final completed =
              data.visits.where((visit) => visit.status == 'COMPLETADA').length;
          final recent = [...data.visits]
            ..sort((a, b) => b.scheduledAt.compareTo(a.scheduledAt));
          final heading = switch (widget.account.role) {
            AppRole.admin => 'Supervisión general',
            AppRole.pastor => 'Tu comunidad pastoral',
            AppRole.leader => 'Mi cuidado pastoral',
          };
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
              children: [
                Text(heading.toUpperCase(),
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          color: AppColors.pine,
                          letterSpacing: 1.1,
                          fontWeight: FontWeight.w800,
                        )),
                const SizedBox(height: 6),
                Text('Resumen operativo',
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 4),
                Text(widget.account.email,
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(color: AppColors.muted)),
                const SizedBox(height: 20),
                LayoutBuilder(
                  builder: (context, constraints) => GridView.count(
                    crossAxisCount: constraints.maxWidth > 640 ? 4 : 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: constraints.maxWidth > 640 ? 1.2 : 1.08,
                    children: [
                      if (widget.account.role == AppRole.admin) ...[
                        _MetricTile(
                          icon: LucideIcons.map,
                          count: '${data.districts.length}',
                          label: 'Distritos',
                          detail: 'Administración global',
                        ),
                        _MetricTile(
                          icon: LucideIcons.church,
                          count:
                              '${data.churches.where((church) => church.active).length}',
                          label: 'Iglesias activas',
                          detail: 'En todos los distritos',
                        ),
                      ],
                      if (widget.account.role != AppRole.leader)
                        _MetricTile(
                          icon: LucideIcons.users,
                          count: '${data.operators.length}',
                          label: widget.account.role == AppRole.admin
                              ? 'Equipo'
                              : 'Líderes',
                          detail: 'Cuentas operativas',
                        ),
                      _MetricTile(
                        icon: LucideIcons.contactRound,
                        count: '${data.brothers.length}',
                        label: 'Hermanos',
                        detail: 'Según tu alcance',
                      ),
                      _MetricTile(
                        icon: LucideIcons.calendarDays,
                        count: '$scheduled',
                        label: 'Programadas',
                        detail: '$completed completadas',
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 26),
                Row(
                  children: [
                    const Icon(LucideIcons.clock3,
                        size: 18, color: AppColors.pine),
                    const SizedBox(width: 8),
                    Text('Actividad de visitas',
                        style: Theme.of(context).textTheme.titleLarge),
                  ],
                ),
                const SizedBox(height: 12),
                if (recent.isEmpty)
                  const _EmptyState(
                    icon: LucideIcons.calendarDays,
                    title: 'Aún no hay visitas',
                    message:
                        'Cuando se registren visitas dentro de tu alcance, aparecerán aquí.',
                  )
                else
                  for (final visit in recent.take(6))
                    _RecentVisitTile(
                      visit: visit,
                      brother: _findBrother(data.brothers, visit.brotherId),
                    ),
                const SizedBox(height: 20),
                _ScopeNote(role: widget.account.role),
              ],
            ),
          );
        },
      );

  Brother? _findBrother(List<Brother> brothers, String id) {
    for (final brother in brothers) {
      if (brother.id == id) return brother;
    }
    return null;
  }
}

class _OverviewData {
  const _OverviewData({
    this.districts = const [],
    this.churches = const [],
    this.operators = const [],
    this.brothers = const [],
    this.visits = const [],
  });

  final List<District> districts;
  final List<Church> churches;
  final List<OperatorProfile> operators;
  final List<Brother> brothers;
  final List<Visit> visits;
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.count,
    required this.label,
    required this.detail,
  });

  final IconData icon;
  final String count;
  final String label;
  final String detail;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppColors.forestSoft,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Icon(icon, color: AppColors.text, size: 19),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(count, style: Theme.of(context).textTheme.headlineSmall),
                  Text(label,
                      style: Theme.of(context)
                          .textTheme
                          .titleSmall
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  Text(detail,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(color: AppColors.muted)),
                ],
              ),
            ],
          ),
        ),
      );
}

class _RecentVisitTile extends StatelessWidget {
  const _RecentVisitTile({required this.visit, required this.brother});

  final Visit visit;
  final Brother? brother;

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (visit.status) {
      'COMPLETADA' => AppColors.pine,
      'CANCELADA' => AppColors.coral,
      _ => AppColors.muted,
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(
          visit.status == 'COMPLETADA'
              ? LucideIcons.circleCheck
              : LucideIcons.calendarDays,
          color: statusColor,
        ),
        title: Text(brother?.fullName ?? 'Registro pastoral'),
        subtitle: Text(
            '${_visitLabel(visit.status)} · ${_formatDate(visit.scheduledAt)}'),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(.1),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            _visitLabel(visit.status),
            style: TextStyle(
                color: statusColor, fontSize: 11, fontWeight: FontWeight.w800),
          ),
        ),
      ),
    );
  }
}

class _ScopeNote extends StatelessWidget {
  const _ScopeNote({required this.role});

  final AppRole role;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
            color: AppColors.soft, borderRadius: BorderRadius.circular(8)),
        child: Row(
          children: [
            const Icon(LucideIcons.shieldCheck,
                color: AppColors.pine, size: 19),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                switch (role) {
                  AppRole.admin =>
                    'Vista global de distritos, iglesias y registros.',
                  AppRole.pastor =>
                    'Los datos se limitan a la iglesia asignada a tu cuenta.',
                  AppRole.leader =>
                    'Los datos se limitan a tus hermanos y visitas asignados.',
                },
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: AppColors.muted),
              ),
            ),
          ],
        ),
      );
}

class _EmptyState extends StatelessWidget {
  const _EmptyState(
      {required this.icon, required this.title, required this.message});

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: [
              Icon(icon, size: 26, color: AppColors.pine),
              const SizedBox(height: 8),
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(message,
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: AppColors.muted)),
            ],
          ),
        ),
      );
}

class _ProblemState extends StatelessWidget {
  const _ProblemState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(LucideIcons.cloudOff,
                  color: AppColors.coral, size: 30),
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(LucideIcons.refreshCw),
                label: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      );
}

String _visitLabel(String status) => switch (status) {
      'COMPLETADA' => 'Completada',
      'CANCELADA' => 'Cancelada',
      _ => 'Programada',
    };

String _formatDate(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
