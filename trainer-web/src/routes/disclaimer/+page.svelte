<svelte:head>
	<title>Disclaimer - Vianasoft Pvt Ltd</title>
</svelte:head>

<div class="legal-shell">
	<header class="legal-header">
		<div class="brand-wrap">
			<img src="/logo.png" alt="Vianasoft logo" class="brand-logo" />
		</div>
		<nav class="header-links" aria-label="Legal pages">
			<span class="header-link current">DISCLAIMER</span>
			<a class="header-link" href="/privacy-policy">PRIVACY POLICY</a>
		</nav>
	</header>

	<main class="legal-main">
		<h1>DISCLAIMER</h1>

		<p>
			The information available on this VQuest platform is provided by Vianasoft Pvt Ltd for academic and training use.
			While we strive to keep content accurate and up to date, we make no warranties or representations of any kind,
			express or implied, about completeness, reliability, suitability, or availability.
		</p>

		<p>
			Any reliance you place on information, generated outputs, analytics, or recommendations is strictly at your own risk.
			Vianasoft Pvt Ltd is not liable for any direct, indirect, incidental, consequential, or special loss or damage,
			including loss of data, interruption of service, or business impact arising from the use of this platform.
		</p>

		<p>
			This platform may include links to third-party websites or services. We do not control and are not responsible for
			the content, security, availability, or policies of external sites. Inclusion of any external link does not imply
			endorsement by Vianasoft Pvt Ltd.
		</p>

		<p>
			Every effort is made to keep VQuest running smoothly. However, temporary unavailability may occur due to maintenance,
			network issues, infrastructure failures, or factors beyond our control. Vianasoft Pvt Ltd assumes no responsibility
			for downtime or resulting impact.
		</p>
	</main>

	<footer class="legal-footer">
		<span>2023 &copy; Vianasoft Pvt Ltd</span>
		<span class="footer-divider">|</span>
		<a href="/disclaimer">Disclaimer</a>
		<span class="footer-divider">|</span>
		<a href="/privacy-policy">Privacy Policy</a>
	</footer>
</div>

<style>
	.legal-shell {
		min-height: 100dvh;
		background: #efefef;
		color: #222;
		display: flex;
		flex-direction: column;
		border: 1px solid #d7d7d7;
	}

	.legal-header {
		height: 82px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 1.25rem;
		border-bottom: 1px solid #dcdcdc;
		background: #f4f4f4;
	}

	.brand-wrap {
		display: flex;
		align-items: center;
	}

	.brand-logo {
		height: 62px;
		width: auto;
		object-fit: contain;
	}

	.header-links {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-family: Georgia, 'Times New Roman', serif;
		font-size: 0.95rem;
		letter-spacing: 0.02em;
	}

	.header-link {
		color: #4a4a4a;
		text-decoration: none;
		font-weight: 700;
	}

	.header-link.current {
		color: #383838;
	}

	.legal-main {
		max-width: 1180px;
		margin: 1.2rem auto 4.5rem;
		padding: 0 2rem;
		font-size: 0.95rem;
		line-height: 1.58;
	}

	.legal-main h1 {
		text-align: center;
		font-size: 2rem;
		letter-spacing: 0.02em;
		font-weight: 500;
		margin: 0.8rem 0 1.75rem;
	}

	.legal-main p {
		margin: 0 0 1.35rem;
	}

	.legal-footer {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		height: 28px;
		background: #39424d;
		color: #b6bec7;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0 0.6rem;
		font-size: 0.74rem;
	}

	.legal-footer a {
		color: #6fb4ff;
		text-decoration: none;
	}

	.legal-footer a:hover {
		text-decoration: underline;
	}

	.footer-divider {
		color: #778190;
	}

	@media (max-width: 760px) {
		.legal-header {
			height: auto;
			padding: 0.75rem;
			align-items: flex-start;
			gap: 0.5rem;
			flex-direction: column;
		}

		.brand-logo {
			height: 50px;
		}

		.header-links {
			font-size: 0.8rem;
		}

		.legal-main {
			padding: 0 1rem;
			font-size: 0.88rem;
			margin-bottom: 4rem;
		}

		.legal-main h1 {
			font-size: 1.5rem;
		}
	}
</style>
