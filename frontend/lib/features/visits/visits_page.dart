import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/time/bogota_time.dart';
import '../../core/theme/app_theme.dart';

class VisitsPage extends StatefulWidget {
  const VisitsPage(
      {required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<VisitsPage> createState() => _VisitsPageState();
}

class _VisitsPageState extends State<VisitsPage> {
  List<Visit> _visits = const [];
  List<Brother> _brothers = const [];
  String _filter = 'TODAS';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await Future.wait<Object>([
        widget.repository.visits(),
        widget.repository.brothers(),
      ]);
      if (!mounted) return;
      setState(() {
        _visits = result[0] as List<Visit>;
        _brothers = result[1] as List<Brother>;
        _loading = false;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = apiErrorMessage(error);
        _loading = false;
      });
    }
  }

  List<Visit> get _visible {
    final visits = _visits
        .where((visit) => _filter == 'TODAS' || visit.status == _filter)
        .toList();
    visits.sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
    return visits;
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
          children: [
            Text(
              widget.account.role == AppRole.leader
                  ? 'Mis visitas'
                  : 'Agenda pastoral',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 5),
            Text('Programadas, completadas y canceladas',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: AppColors.muted)),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              children: [
                _filterChip('TODAS', 'Todas'),
                _filterChip('PROGRAMADA', 'Programadas'),
                _filterChip('COMPLETADA', 'Completadas'),
                _filterChip('CANCELADA', 'Canceladas'),
              ],
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _loading ? null : _createVisit,
                icon: const Icon(LucideIcons.plus),
                label: const Text('Nueva visita'),
              ),
            ),
            const SizedBox(height: 12),
            if (_error != null) _errorPanel(_error!),
            if (_loading) const LinearProgressIndicator(),
            if (!_loading && _error == null && _visible.isEmpty)
              const _EmptyVisits(),
            if (!_loading && _error == null)
              for (final visit in _visible)
                _visitCard(visit, _brotherById(visit.brotherId)),
          ],
        ),
      );

  Widget _filterChip(String value, String label) => ChoiceChip(
        label: Text(label),
        selected: _filter == value,
        onSelected: (_) => setState(() => _filter = value),
      );

  Widget _visitCard(Visit visit, Brother? brother) {
    final color = switch (visit.status) {
      'COMPLETADA' => AppColors.pine,
      'CANCELADA' => AppColors.coral,
      _ => AppColors.forest,
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_iconFor(visit.status), color: color, size: 20),
                const SizedBox(width: 9),
                Expanded(
                    child: Text(brother?.fullName ?? 'Registro pastoral',
                        style: Theme.of(context).textTheme.titleMedium)),
                _StatusTag(status: visit.status),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                _Meta(
                    icon: LucideIcons.calendarDays,
                    text: DateFormat('dd/MM/yyyy · hh:mm a', 'es_CO')
                        .format(BogotaTime.display(visit.scheduledAt))),
                _Meta(
                    icon: LucideIcons.clock3,
                    text: '${visit.durationMinutes} min'),
              ],
            ),
            const SizedBox(height: 8),
            _Meta(icon: LucideIcons.mapPin, text: visit.location),
            const SizedBox(height: 8),
            Text(_visitType(visit.visitType),
                style: Theme.of(context)
                    .textTheme
                    .labelMedium
                    ?.copyWith(color: AppColors.pine)),
            if (visit.status == 'CANCELADA' &&
                visit.cancellationReason != null) ...[
              const SizedBox(height: 8),
              Text('Motivo: ${visit.cancellationReason}',
                  style: Theme.of(context).textTheme.bodySmall),
            ],
            if (widget.account.role != AppRole.leader) ...[
              const SizedBox(height: 6),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: () => _showHistory(visit),
                  icon: const Icon(LucideIcons.history, size: 17),
                  label: const Text('Historial'),
                ),
              ),
            ],
            if (visit.status == 'PROGRAMADA') ...[
              const Divider(height: 22),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.tonalIcon(
                    onPressed: () => _complete(visit),
                    icon: const Icon(LucideIcons.circleCheck, size: 17),
                    label: const Text('Completar'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _reschedule(visit),
                    icon: const Icon(LucideIcons.calendarClock, size: 17),
                    label: const Text('Reprogramar'),
                  ),
                  TextButton.icon(
                    onPressed: () => _cancel(visit),
                    icon: const Icon(LucideIcons.circleX, size: 17),
                    label: const Text('Cancelar'),
                    style:
                        TextButton.styleFrom(foregroundColor: AppColors.coral),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _createVisit() async {
    final eligible = _brothers.where((brother) => brother.active).toList();
    if (eligible.isEmpty) {
      _message(
          'No hay hermanos activos en tu alcance para programar una visita.');
      return;
    }
    final result = await _visitForm(eligible);
    if (result == null) return;
    try {
      await widget.repository.createVisit(
        brotherId: result.brotherId,
        visitType: result.type,
        scheduledAt: result.scheduledAt,
        durationMinutes: result.duration,
        location: result.location,
        observations: result.observations,
      );
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<_VisitForm?> _visitForm(List<Brother> brothers) async {
    String brotherId = brothers.first.id;
    String type = 'EVANGELISMO';
    var duration = 45;
    var scheduledAt = BogotaTime.now().add(const Duration(days: 1));
    final location = TextEditingController();
    final observations = TextEditingController();
    final result = await showDialog<_VisitForm>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, refresh) => AlertDialog(
          title: const Text('Programar visita'),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    value: brotherId,
                    decoration: const InputDecoration(labelText: 'Hermano'),
                    items: [
                      for (final item in brothers)
                        DropdownMenuItem(
                            value: item.id, child: Text(item.fullName))
                    ],
                    onChanged: (value) => refresh(() => brotherId = value!),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: type,
                    decoration:
                        const InputDecoration(labelText: 'Tipo de visita'),
                    items: const [
                      DropdownMenuItem(
                          value: 'EVANGELISMO', child: Text('Evangelismo')),
                      DropdownMenuItem(
                          value: 'ENSENANZA', child: Text('Enseñanza')),
                      DropdownMenuItem(
                          value: 'CUIDADO_PASTORAL',
                          child: Text('Cuidado pastoral')),
                    ],
                    onChanged: (value) => refresh(() => type = value!),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () async {
                      final day = await showDatePicker(
                        context: context,
                        initialDate: scheduledAt,
                        firstDate: BogotaTime.now(),
                        lastDate:
                            BogotaTime.now().add(const Duration(days: 730)),
                      );
                      if (day == null || !context.mounted) return;
                      final time = await showTimePicker(
                          context: context,
                          initialTime: TimeOfDay.fromDateTime(scheduledAt));
                      if (time == null) return;
                      refresh(() => scheduledAt = BogotaTime.wallClockToUtc(
                            year: day.year,
                            month: day.month,
                            day: day.day,
                            hour: time.hour,
                            minute: time.minute,
                          ));
                    },
                    icon: const Icon(LucideIcons.calendarClock),
                    label: Text(DateFormat('dd/MM/yyyy · hh:mm a', 'es_CO')
                        .format(BogotaTime.display(scheduledAt))),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    value: duration,
                    decoration: const InputDecoration(labelText: 'Duración'),
                    items: const [30, 45, 60, 90]
                        .map((value) => DropdownMenuItem(
                            value: value, child: Text('$value minutos')))
                        .toList(),
                    onChanged: (value) => refresh(() => duration = value!),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                      controller: location,
                      decoration: const InputDecoration(labelText: 'Lugar')),
                  const SizedBox(height: 10),
                  TextField(
                      controller: observations,
                      minLines: 2,
                      maxLines: 4,
                      decoration:
                          const InputDecoration(labelText: 'Observaciones')),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancelar')),
            FilledButton(
              onPressed: () {
                if (location.text.trim().isEmpty ||
                    observations.text.trim().isEmpty) return;
                Navigator.pop(
                    dialogContext,
                    _VisitForm(
                      brotherId: brotherId,
                      type: type,
                      scheduledAt: scheduledAt,
                      duration: duration,
                      location: location.text.trim(),
                      observations: observations.text.trim(),
                    ));
              },
              child: const Text('Programar'),
            ),
          ],
        ),
      ),
    );
    location.dispose();
    observations.dispose();
    return result;
  }

  Future<void> _complete(Visit visit) async {
    if (!await _confirm('¿Marcar esta visita como completada?')) return;
    try {
      await widget.repository.updateVisit(visit.id, {'status': 'COMPLETADA'});
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _showHistory(Visit visit) async {
    final history = widget.repository.visitHistory(visit.id);
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Historial de la visita'),
        content: SizedBox(
          width: 480,
          height: 360,
          child: FutureBuilder<List<VisitHistoryEntry>>(
            future: history,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Center(child: Text(apiErrorMessage(snapshot.error!)));
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.data!.isEmpty) {
                return const Center(
                    child:
                        Text('No hay cambios registrados para esta visita.'));
              }
              return ListView.separated(
                itemCount: snapshot.data!.length,
                separatorBuilder: (_, __) => const Divider(height: 18),
                itemBuilder: (context, index) =>
                    _HistoryEntryTile(entry: snapshot.data![index]),
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  Future<void> _reschedule(Visit visit) async {
    final day = await showDatePicker(
      context: context,
      initialDate:
          BogotaTime.display(visit.scheduledAt).isAfter(BogotaTime.now())
              ? BogotaTime.display(visit.scheduledAt)
              : BogotaTime.now().add(const Duration(days: 1)),
      firstDate: BogotaTime.now(),
      lastDate: BogotaTime.now().add(const Duration(days: 730)),
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.fromDateTime(visit.scheduledAt));
    if (time == null) return;
    final date = BogotaTime.wallClockToUtc(
      year: day.year,
      month: day.month,
      day: day.day,
      hour: time.hour,
      minute: time.minute,
    );
    try {
      await widget.repository.updateVisit(visit.id, {
        'scheduled_at': date.toIso8601String(),
      });
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Future<void> _cancel(Visit visit) async {
    final reason = TextEditingController();
    final accepted = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancelar visita'),
        content: TextField(
          controller: reason,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Motivo de cancelación'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Volver')),
          FilledButton(
            onPressed: () {
              if (reason.text.trim().isNotEmpty) {
                Navigator.pop(dialogContext, reason.text.trim());
              }
            },
            style: FilledButton.styleFrom(backgroundColor: AppColors.coral),
            child: const Text('Cancelar visita'),
          ),
        ],
      ),
    );
    reason.dispose();
    if (accepted == null) return;
    try {
      await widget.repository.cancelVisit(visit.id, accepted);
      await _load();
    } on Object catch (error) {
      _message(apiErrorMessage(error));
    }
  }

  Brother? _brotherById(String id) {
    for (final brother in _brothers) {
      if (brother.id == id) return brother;
    }
    return null;
  }

  Future<bool> _confirm(String text) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirmar cambio'),
          content: Text(text),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Volver')),
            FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Confirmar')),
          ],
        ),
      ) ??
      false;

  void _message(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Widget _errorPanel(String message) => Card(
        color: AppColors.coralSoft,
        child: ListTile(
          leading:
              const Icon(LucideIcons.triangleAlert, color: AppColors.coral),
          title: Text(message),
          trailing: IconButton(
              onPressed: _load, icon: const Icon(LucideIcons.refreshCw)),
        ),
      );
}

class _VisitForm {
  const _VisitForm({
    required this.brotherId,
    required this.type,
    required this.scheduledAt,
    required this.duration,
    required this.location,
    required this.observations,
  });

  final String brotherId;
  final String type;
  final DateTime scheduledAt;
  final int duration;
  final String location;
  final String observations;
}

class _StatusTag extends StatelessWidget {
  const _StatusTag({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'COMPLETADA' => AppColors.pine,
      'CANCELADA' => AppColors.coral,
      _ => AppColors.forest,
    };
    final label = switch (status) {
      'COMPLETADA' => 'COMPLETADA',
      'CANCELADA' => 'CANCELADA',
      _ => 'PROGRAMADA',
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
          color: color.withOpacity(.1), borderRadius: BorderRadius.circular(4)),
      child: Text(label,
          style: TextStyle(
              color: color, fontSize: 10, fontWeight: FontWeight.w800)),
    );
  }
}

class _HistoryEntryTile extends StatelessWidget {
  const _HistoryEntryTile({required this.entry});

  final VisitHistoryEntry entry;

  @override
  Widget build(BuildContext context) {
    final changes = <String>[];
    if (entry.previousStatus != null || entry.newStatus != null) {
      changes.add('${entry.previousStatus ?? '—'} → ${entry.newStatus ?? '—'}');
    }
    if (entry.previousScheduledAt != null || entry.newScheduledAt != null) {
      changes.add(
        '${_formatHistoryDate(entry.previousScheduledAt)} → ${_formatHistoryDate(entry.newScheduledAt)}',
      );
    }
    for (final field in {
      ...?entry.previousValues?.keys,
      ...?entry.newValues?.keys,
    }) {
      final normalizedField = field.toLowerCase();
      if (field == 'scheduled_at' ||
          normalizedField.contains('token') ||
          normalizedField.contains('password') ||
          normalizedField.contains('hash')) continue;
      final previous = entry.previousValues?[field];
      final current = entry.newValues?[field];
      if (previous != current) {
        changes.add(
          '${_historyFieldLabel(field)}: ${previous ?? '—'} → ${current ?? '—'}',
        );
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _historyActionLabel(entry.action),
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 3),
        Text(
          DateFormat('dd/MM/yyyy · HH:mm', 'es_CO')
              .format(BogotaTime.display(entry.createdAt)),
          style: Theme.of(context)
              .textTheme
              .bodySmall
              ?.copyWith(color: AppColors.muted),
        ),
        const SizedBox(height: 3),
        Text(
          'Actor ${entry.actorId.length > 8 ? entry.actorId.substring(0, 8) : entry.actorId}',
          style: Theme.of(context)
              .textTheme
              .bodySmall
              ?.copyWith(color: AppColors.muted),
        ),
        for (final change in changes) ...[
          const SizedBox(height: 5),
          Text(change, style: Theme.of(context).textTheme.bodySmall),
        ],
        if (entry.reason != null && entry.reason!.isNotEmpty) ...[
          const SizedBox(height: 5),
          Text('Motivo: ${entry.reason}',
              style: Theme.of(context).textTheme.bodySmall),
        ],
      ],
    );
  }
}

String _formatHistoryDate(DateTime? value) => value == null
    ? '—'
    : DateFormat('dd/MM/yyyy · HH:mm', 'es_CO')
        .format(BogotaTime.display(value));

String _historyActionLabel(String action) => switch (action) {
      'CREADA' => 'Visita creada',
      'MODIFICADA' => 'Visita modificada',
      'COMPLETADA' => 'Visita completada',
      'REPROGRAMADA' => 'Visita reprogramada',
      'CANCELADA' => 'Visita cancelada',
      _ => action.replaceAll('_', ' ').toLowerCase(),
    };

String _historyFieldLabel(String field) => switch (field) {
      'visit_type' => 'Tipo',
      'duration_minutes' => 'Duración',
      'location' => 'Lugar',
      'observations' => 'Observaciones',
      'cancellation_reason' => 'Motivo de cancelación',
      _ => field,
    };

class _Meta extends StatelessWidget {
  const _Meta({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: AppColors.pine),
          const SizedBox(width: 5),
          Text(text, style: Theme.of(context).textTheme.bodySmall),
        ],
      );
}

class _EmptyVisits extends StatelessWidget {
  const _EmptyVisits();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.only(top: 40),
        child: Column(
          children: [
            Icon(LucideIcons.calendarDays, size: 28, color: AppColors.pine),
            SizedBox(height: 10),
            Text('No hay visitas con este filtro.'),
          ],
        ),
      );
}

IconData _iconFor(String status) => switch (status) {
      'COMPLETADA' => LucideIcons.circleCheck,
      'CANCELADA' => LucideIcons.circleX,
      _ => LucideIcons.calendarDays,
    };

String _visitType(String value) => switch (value) {
      'EVANGELISMO' => 'Evangelismo',
      'ENSENANZA' => 'Enseñanza',
      _ => 'Cuidado pastoral',
    };
