import 'package:flutter/material.dart';
import '../app.dart';

/// Shimmer loading effect for skeleton screens.
class ShimmerLoading extends StatefulWidget {
  final Widget child;
  final bool enabled;

  const ShimmerLoading({
    super.key,
    required this.child,
    this.enabled = true,
  });

  @override
  State<ShimmerLoading> createState() => _ShimmerLoadingState();
}

class _ShimmerLoadingState extends State<ShimmerLoading>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) return widget.child;

    return _ShimmerWidget(
      controller: _controller,
      child: widget.child,
    );
  }
}

class _ShimmerWidget extends AnimatedWidget {
  final Widget child;

  const _ShimmerWidget({
    required AnimationController controller,
    required this.child,
  }) : super(listenable: controller);

  Animation<double> get _progress => listenable as Animation<double>;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.srcATop,
      shaderCallback: (bounds) {
        final dx = bounds.width * _progress.value;
        return LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: const [
            Color(0xFF1C2128),
            Color(0xFF2A3038),
            Color(0xFF1C2128),
          ],
          stops: [
            (dx / bounds.width - 0.3).clamp(0.0, 1.0),
            (dx / bounds.width).clamp(0.0, 1.0),
            (dx / bounds.width + 0.3).clamp(0.0, 1.0),
          ],
        ).createShader(bounds);
      },
      child: child,
    );
  }
}

/// A skeleton box placeholder for loading states.
class SkeletonBox extends StatelessWidget {
  final double? width;
  final double? height;
  final BorderRadius? borderRadius;

  const SkeletonBox({
    super.key,
    this.width,
    this.height = 16,
    this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: borderRadius ?? BorderRadius.circular(6),
      ),
    );
  }
}

/// Shimmer skeleton for a card-like container.
class SkeletonCard extends StatelessWidget {
  final double height;
  final EdgeInsets margin;

  const SkeletonCard({
    super.key,
    this.height = 100,
    this.margin = const EdgeInsets.only(bottom: 12),
  });

  @override
  Widget build(BuildContext context) {
    return ShimmerLoading(
      child: Container(
        height: height,
        margin: margin,
        decoration: BoxDecoration(
          color: AlphaStackApp.cardDark,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AlphaStackApp.borderDark),
        ),
      ),
    );
  }
}
