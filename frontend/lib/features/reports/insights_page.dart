import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/time/bogota_time.dart';
import '../../core/theme/app_theme.dart';

class AuditPage extends StatefulWidget {
  const AuditPage({required this.repository, super.key});

  final ApiRepository repository;

  @override
  State<AuditPage> createState() => _AuditPageState();
}

class _AuditPageState extends State<AuditPage> {
  late Future<List<AuditEvent>> _events;

  @override
  void initState() {
    super.initState();
    _events = widget.repository.audit();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Auditoría pastoral')),
        body: FutureBuilder<List<AuditEvent>>(
          future: _events,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return _LoadError(
                  message: apiErrorMessage(snapshot.error!), onRetry: _reload);
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final events = snapshot.data!;
            if (events.isEmpty) {
              return const _EmptyReport(
                icon: LucideIcons.clipboardList,
                text:
                    'No hay eventos de auditoría disponibles en este alcance.',
              );
            }
            return RefreshIndicator(
              onRefresh: _reload,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: events.length,
                itemBuilder: (context, index) =>
                    _AuditCard(event: events[index]),
              ),
            );
          },
        ),
      );

  Future<void> _reload() async {
    final next = widget.repository.audit();
    setState(() => _events = next);
    await next;
  }
}

class _AuditCard extends StatelessWidget {
  const _AuditCard({required this.event});

  final AuditEvent event;

  @override
  Widget build(BuildContext context) {
    final values = _safeValues(event.previousValues, event.newValues);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(LucideIcons.history,
                    color: AppColors.pine, size: 19),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(event.resource,
                        style: Theme.of(context).textTheme.titleMedium)),
                Text(
                    DateFormat('dd/MM/yy · HH:mm')
                        .format(BogotaTime.display(event.createdAt)),
                    style: Theme.of(context)
                        .textTheme
                        .labelSmall
                        ?.copyWith(color: AppColors.muted)),
              ],
            ),
            const SizedBox(height: 5),
            Text(_actionLabel(event.action),
                style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 7),
            Text(
                'Actor ${_shortId(event.actorId)} · Registro ${_shortId(event.resourceId)}',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: AppColors.muted)),
            if (values.isNotEmpty) ...[
              const Divider(height: 20),
              for (final entry in values.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('${entry.key}: ${entry.value}',
                      style: Theme.of(context).textTheme.bodySmall),
                ),
            ],
            if (event.reason != null && event.reason!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Motivo: ${event.reason}',
                  style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

Map<String, String> _safeValues(
  Map<String, dynamic>? previous,
  Map<String, dynamic>? current,
) {
  final output = <String, String>{};
  for (final source in [previous, current]) {
    if (source == null) continue;
    for (final entry in source.entries) {
      final key = entry.key.toLowerCase();
      if (key.contains('password') ||
          key.contains('hash') ||
          key.contains('token')) continue;
      output[entry.key] = entry.value is Map || entry.value is List
          ? jsonEncode(entry.value)
          : '${entry.value ?? '—'}';
    }
  }
  return output;
}

String _actionLabel(String action) => action.replaceAll('_', ' ').toLowerCase();
String _shortId(String value) =>
    value.length > 8 ? value.substring(0, 8) : value;

class RankingPage extends StatefulWidget {
  const RankingPage(
      {required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<RankingPage> createState() => _RankingPageState();
}

class _RankingPageState extends State<RankingPage> {
  String _period = 'MES';
  String? _churchId;
  List<Church> _churches = const [];
  Future<List<RankingEntry>>? _ranking;
  bool _loadingChurches = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.account.role == AppRole.pastor) {
      _churchId = widget.account.churchId;
      _loadRanking();
    } else {
      _loadChurches();
    }
  }

  Future<void> _loadChurches() async {
    setState(() => _loadingChurches = true);
    try {
      final churches = await widget.repository.churches();
      if (!mounted) return;
      setState(() {
        _churches = churches.where((church) => church.active).toList();
        _churchId ??= _churches.firstOrNull?.id;
        _loadingChurches = false;
      });
      _loadRanking();
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = apiErrorMessage(error);
        _loadingChurches = false;
      });
    }
  }

  void _loadRanking() {
    final churchId = _churchId;
    if (churchId == null) {
      setState(() => _ranking = null);
      return;
    }
    setState(() {
      _error = null;
      _ranking = widget.repository.ranking(period: _period, churchId: churchId);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Ranking pastoral')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Visitas completadas por período',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: AppColors.muted)),
            const SizedBox(height: 14),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'SEMANA', label: Text('Semana')),
                ButtonSegment(value: 'MES', label: Text('Mes')),
              ],
              selected: {_period},
              onSelectionChanged: (value) {
                setState(() => _period = value.first);
                _loadRanking();
              },
            ),
            if (widget.account.role == AppRole.admin) ...[
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _churchId,
                decoration: const InputDecoration(labelText: 'Iglesia'),
                items: [
                  for (final church in _churches)
                    DropdownMenuItem(value: church.id, child: Text(church.name))
                ],
                onChanged: (value) {
                  setState(() => _churchId = value);
                  _loadRanking();
                },
              ),
            ],
            const SizedBox(height: 16),
            if (_error != null)
              _LoadError(message: _error!, onRetry: _loadChurches),
            if (_loadingChurches) const LinearProgressIndicator(),
            if (_churchId == null && !_loadingChurches)
              const _EmptyReport(
                  icon: LucideIcons.church,
                  text: 'Selecciona una iglesia para consultar el ranking.'),
            if (_ranking != null)
              FutureBuilder<List<RankingEntry>>(
                future: _ranking,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return _LoadError(
                        message: apiErrorMessage(snapshot.error!),
                        onRetry: _loadRanking);
                  }
                  if (!snapshot.hasData) {
                    return const Center(
                        child: Padding(
                            padding: EdgeInsets.all(28),
                            child: CircularProgressIndicator()));
                  }
                  if (snapshot.data!.isEmpty) {
                    return const _EmptyReport(
                        icon: LucideIcons.chartNoAxesCombined,
                        text:
                            'Aún no hay visitas completadas en este período.');
                  }
                  return Column(
                    children: [
                      for (final entry in snapshot.data!)
                        Card(
                          margin: const EdgeInsets.only(bottom: 9),
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: entry.position == 1
                                  ? AppColors.mint
                                  : AppColors.soft,
                              child: Text('${entry.position}',
                                  style: const TextStyle(
                                      color: AppColors.forest,
                                      fontWeight: FontWeight.w800)),
                            ),
                            title: Text(entry.leaderName),
                            subtitle: Text(
                                '${entry.completedVisits} visitas completadas'),
                            trailing: entry.position == 1
                                ? const Icon(LucideIcons.badgeCheck,
                                    color: AppColors.pine)
                                : null,
                          ),
                        ),
                    ],
                  );
                },
              ),
          ],
        ),
      );
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Card(
        color: AppColors.coralSoft,
        child: ListTile(
          leading:
              const Icon(LucideIcons.triangleAlert, color: AppColors.coral),
          title: Text(message),
          trailing: IconButton(
              onPressed: onRetry, icon: const Icon(LucideIcons.refreshCw)),
        ),
      );
}

class _EmptyReport extends StatelessWidget {
  const _EmptyReport({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 32),
        child: Column(
          children: [
            Icon(icon, size: 28, color: AppColors.pine),
            const SizedBox(height: 9),
            Text(text, textAlign: TextAlign.center),
          ],
        ),
      );
}
