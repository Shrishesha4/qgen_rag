<svelte:head>
	<title>Privacy Policy - Vianasoft Pvt Ltd</title>
</svelte:head>

<div class="legal-shell">
	<header class="legal-header">
		<div class="brand-wrap">
			<img src="/logo.png" alt="Vianasoft logo" class="brand-logo" />
		</div>
		<nav class="header-links" aria-label="Legal pages">
			<a class="header-link" href="/disclaimer">DISCLAIMER</a>
			<span class="header-link current">PRIVACY POLICY</span>
		</nav>
	</header>

	<main class="legal-main">
		<h1>PRIVACY POLICY</h1>

		<p>
			Your privacy matters to us. This policy explains how Vianasoft Pvt Ltd collects, uses, stores, and protects
			information when you use the VQuest platform.
		</p>

		<h2>Information We Collect</h2>
		<p>
			We may collect account details (such as name, email, role, and organization), usage data (such as pages visited,
			actions performed, and timestamps), and technical metadata (such as browser, device, and IP address) to support
			platform operations, quality, and security.
		</p>

		<h2>How We Use Information</h2>
		<p>
			Information is used to authenticate users, deliver product features, improve question-generation quality,
			maintain service reliability, communicate important updates, and meet legal or compliance obligations.
			We only process data for legitimate business and operational purposes.
		</p>

		<h2>Data Sharing</h2>
		<p>
			Vianasoft Pvt Ltd does not sell personal information. We may share limited data with trusted service providers
			who assist with hosting, analytics, monitoring, and support, under appropriate contractual and security controls.
		</p>

		<h2>Security and Retention</h2>
		<p>
			We implement technical and organizational safeguards to protect data from unauthorized access, misuse, or loss.
			Data is retained only for as long as necessary for service operation, contractual commitments, and legal requirements.
		</p>

		<h2>Your Rights</h2>
		<p>
			Depending on your jurisdiction, you may request access, correction, or deletion of personal data.
			For privacy requests or concerns, contact Vianasoft support through your authorized organization channel.
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

	.legal-main h2 {
		font-size: 1.06rem;
		margin: 0 0 0.35rem;
		font-weight: 700;
	}

	.legal-main p {
		margin: 0 0 1.2rem;
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
