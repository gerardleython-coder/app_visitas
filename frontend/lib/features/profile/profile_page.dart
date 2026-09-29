import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/models/api_models.dart';
import '../../core/network/api_repository.dart';
import '../../core/session/session_cubit.dart';
import '../../core/theme/app_theme.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage(
      {required this.account, required this.repository, super.key});

  final CurrentAccount account;
  final ApiRepository repository;

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  bool _changingPassword = false;
  String? _error;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Perfil y seguridad')),
        body: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const CircleAvatar(
                      radius: 25,
                      backgroundColor: AppColors.soft,
                      child:
                          Icon(LucideIcons.userRound, color: AppColors.forest),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(widget.account.email,
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 4),
                          Text(widget.account.role.apiValue,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelMedium
                                  ?.copyWith(color: AppColors.pine)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text('Seguridad', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 9),
            Card(
              child: ListTile(
                leading:
                    const Icon(LucideIcons.lockKeyhole, color: AppColors.pine),
                title: const Text('Cambiar contraseña'),
                subtitle:
                    const Text('Se cerrarán las sesiones activas al guardar.'),
                trailing: const Icon(LucideIcons.chevronRight),
                onTap: _changingPassword ? null : _changePassword,
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(_error!, style: const TextStyle(color: AppColors.coral)),
            ],
            const SizedBox(height: 26),
            OutlinedButton.icon(
              onPressed: () async {
                await context.read<SessionCubit>().signOut();
              },
              icon: const Icon(LucideIcons.logOut),
              label: const Text('Cerrar sesión'),
            ),
          ],
        ),
      );

  Future<void> _changePassword() async {
    final current = TextEditingController();
    final next = TextEditingController();
    final confirm = TextEditingController();
    final result = await showDialog<(String, String)>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cambiar contraseña'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
                controller: current,
                obscureText: true,
                decoration:
                    const InputDecoration(labelText: 'Contraseña actual')),
            const SizedBox(height: 10),
            TextField(
                controller: next,
                obscureText: true,
                decoration:
                    const InputDecoration(labelText: 'Nueva contraseña')),
            const SizedBox(height: 10),
            TextField(
                controller: confirm,
                obscureText: true,
                decoration: const InputDecoration(
                    labelText: 'Confirmar nueva contraseña')),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              if (current.text.isNotEmpty &&
                  next.text.isNotEmpty &&
                  next.text == confirm.text) {
                Navigator.pop(dialogContext, (current.text, next.text));
              }
            },
            child: const Text('Actualizar'),
          ),
        ],
      ),
    );
    current.dispose();
    next.dispose();
    confirm.dispose();
    if (result == null) return;
    if (!mounted) return;
    final session = context.read<SessionCubit>();
    setState(() {
      _changingPassword = true;
      _error = null;
    });
    try {
      await session.changePassword(result.$1, result.$2);
    } on Object catch (error) {
      if (mounted) setState(() => _error = apiErrorMessage(error));
    } finally {
      if (mounted) setState(() => _changingPassword = false);
    }
  }
}
