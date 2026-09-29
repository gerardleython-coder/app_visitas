import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/network/api_repository.dart';
import '../../core/session/session_cubit.dart';
import '../../core/theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, this.error});

  final String? error;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _recoveryEmailController = TextEditingController();
  final _recoveryTokenController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _showPassword = false;
  bool _recovering = false;
  bool _resetting = false;
  bool _recoverySent = false;
  bool _recoveryBusy = false;
  String? _recoveryError;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _recoveryEmailController.dispose();
    _recoveryTokenController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _brand(),
                    const SizedBox(height: 28),
                    _accessNote(),
                    if (widget.error != null && !_recovering) ...[
                      const SizedBox(height: 12),
                      _errorBanner(widget.error!),
                    ],
                    const SizedBox(height: 16),
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 180),
                      child: !_recovering
                          ? _loginForm()
                          : _resetting
                              ? _resetForm()
                              : _recoveryForm(),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Acceso exclusivo para cuentas operativas activas.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.muted,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

  Widget _brand() => Column(
        children: [
          SvgPicture.asset('assets/appvisitas_logo.svg', width: 72, height: 72),
          const SizedBox(height: 10),
          Text('AppVisitas', style: Theme.of(context).textTheme.headlineMedium),
          Text(
            'Gestión y cuidado pastoral',
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(color: AppColors.muted),
          ),
        ],
      );

  Widget _accessNote() => DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.soft,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.line),
        ),
        child: const Padding(
          padding: EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(LucideIcons.shieldCheck, color: AppColors.pine, size: 20),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Tu rol y tu alcance territorial se validan con tu cuenta activa.',
                  style: TextStyle(color: AppColors.text, height: 1.45),
                ),
              ),
            ],
          ),
        ),
      );

  Widget _loginForm() => Card(
        key: const ValueKey('login'),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Iniciar sesión',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 18),
                TextFormField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.username],
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Correo institucional',
                    prefixIcon: Icon(LucideIcons.mail),
                  ),
                  validator: (value) => value == null || !value.contains('@')
                      ? 'Ingresa un correo válido.'
                      : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _passwordController,
                  obscureText: !_showPassword,
                  autofillHints: const [AutofillHints.password],
                  textInputAction: TextInputAction.done,
                  onFieldSubmitted: (_) => _submitLogin(),
                  decoration: InputDecoration(
                    labelText: 'Contraseña',
                    prefixIcon: const Icon(LucideIcons.lockKeyhole),
                    suffixIcon: IconButton(
                      tooltip: _showPassword
                          ? 'Ocultar contraseña'
                          : 'Mostrar contraseña',
                      onPressed: () =>
                          setState(() => _showPassword = !_showPassword),
                      icon: Icon(
                          _showPassword ? LucideIcons.eyeOff : LucideIcons.eye),
                    ),
                  ),
                  validator: (value) => value == null || value.isEmpty
                      ? 'Ingresa tu contraseña.'
                      : null,
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => setState(() {
                      _recovering = true;
                      _recoverySent = false;
                      _recoveryError = null;
                    }),
                    child: const Text('¿Olvidaste tu contraseña?'),
                  ),
                ),
                const SizedBox(height: 6),
                BlocBuilder<SessionCubit, SessionState>(
                  builder: (context, state) => FilledButton.icon(
                    onPressed: state.status == SessionStatus.checking
                        ? null
                        : _submitLogin,
                    icon: state.status == SessionStatus.checking
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(LucideIcons.logIn),
                    label: Text(
                      state.status == SessionStatus.checking
                          ? 'Ingresando'
                          : 'Ingresar',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );

  Widget _recoveryForm() => Card(
        key: const ValueKey('recovery'),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  IconButton(
                    tooltip: 'Volver a iniciar sesión',
                    onPressed: () => setState(() => _recovering = false),
                    icon: const Icon(LucideIcons.arrowLeft),
                  ),
                  Expanded(
                    child: Text('Recuperar acceso',
                        style: Theme.of(context).textTheme.titleLarge),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Si el correo corresponde a una cuenta activa, enviaremos instrucciones.',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: AppColors.muted),
              ),
              const SizedBox(height: 18),
              TextField(
                controller: _recoveryEmailController,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'Correo institucional',
                  prefixIcon: Icon(LucideIcons.mail),
                ),
              ),
              if (_recoveryError != null) ...[
                const SizedBox(height: 12),
                _errorBanner(_recoveryError!),
              ],
              if (_recoverySent) ...[
                const SizedBox(height: 12),
                const _InfoBanner(
                  icon: LucideIcons.circleCheck,
                  text:
                      'Solicitud recibida. Si la cuenta existe, recibirás un correo.',
                ),
                const SizedBox(height: 6),
                TextButton(
                  onPressed: () => setState(() {
                    _resetting = true;
                    _recoveryError = null;
                  }),
                  child: const Text('Ya tengo el token de recuperación'),
                ),
              ],
              const SizedBox(height: 18),
              FilledButton.icon(
                onPressed: _recoveryBusy ? null : _submitRecovery,
                icon: _recoveryBusy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(LucideIcons.send),
                label: const Text('Enviar solicitud'),
              ),
            ],
          ),
        ),
      );

  Widget _resetForm() => Card(
        key: const ValueKey('reset'),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  IconButton(
                    tooltip: 'Volver a recuperación',
                    onPressed: () => setState(() => _resetting = false),
                    icon: const Icon(LucideIcons.arrowLeft),
                  ),
                  Expanded(
                    child: Text('Definir nueva contraseña',
                        style: Theme.of(context).textTheme.titleLarge),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _recoveryTokenController,
                decoration: const InputDecoration(
                    labelText: 'Token recibido por correo'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _newPasswordController,
                obscureText: true,
                decoration:
                    const InputDecoration(labelText: 'Nueva contraseña'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _confirmPasswordController,
                obscureText: true,
                decoration:
                    const InputDecoration(labelText: 'Confirmar contraseña'),
              ),
              if (_recoveryError != null) ...[
                const SizedBox(height: 12),
                _errorBanner(_recoveryError!),
              ],
              const SizedBox(height: 18),
              FilledButton.icon(
                onPressed: _recoveryBusy ? null : _submitReset,
                icon: _recoveryBusy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(LucideIcons.keyRound),
                label: const Text('Actualizar contraseña'),
              ),
            ],
          ),
        ),
      );

  Widget _errorBanner(String message) => DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.coralSoft,
          borderRadius: BorderRadius.circular(6),
          border:
              const Border(left: BorderSide(color: AppColors.coral, width: 3)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(LucideIcons.triangleAlert,
                  color: AppColors.coral, size: 18),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(message,
                      style: const TextStyle(color: AppColors.text))),
            ],
          ),
        ),
      );

  Future<void> _submitLogin() async {
    if (!_formKey.currentState!.validate()) return;
    await context
        .read<SessionCubit>()
        .signIn(_emailController.text, _passwordController.text);
  }

  Future<void> _submitRecovery() async {
    final email = _recoveryEmailController.text.trim();
    if (!email.contains('@')) {
      setState(() => _recoveryError = 'Ingresa un correo válido.');
      return;
    }
    setState(() {
      _recoveryBusy = true;
      _recoveryError = null;
    });
    try {
      await context.read<SessionCubit>().requestPasswordReset(email);
      setState(() => _recoverySent = true);
    } on Object {
      setState(() =>
          _recoveryError = 'No se pudo enviar la solicitud. Intenta de nuevo.');
    } finally {
      if (mounted) setState(() => _recoveryBusy = false);
    }
  }

  Future<void> _submitReset() async {
    final token = _recoveryTokenController.text.trim();
    final password = _newPasswordController.text;
    if (token.isEmpty ||
        password.isEmpty ||
        password != _confirmPasswordController.text) {
      setState(() => _recoveryError =
          'Revisa el token y confirma que las contraseñas coincidan.');
      return;
    }
    setState(() {
      _recoveryBusy = true;
      _recoveryError = null;
    });
    try {
      await context.read<SessionCubit>().resetPassword(token, password);
      if (!mounted) return;
      setState(() {
        _recovering = false;
        _resetting = false;
      });
    } on Object catch (error) {
      if (mounted) setState(() => _recoveryError = apiErrorMessage(error));
    } finally {
      if (mounted) setState(() => _recoveryBusy = false);
    }
  }
}

class _InfoBanner extends StatelessWidget {
  const _InfoBanner({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.soft,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(icon, color: AppColors.pine, size: 18),
              const SizedBox(width: 8),
              Expanded(child: Text(text)),
            ],
          ),
        ),
      );
}
